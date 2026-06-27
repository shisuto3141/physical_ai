# Alice — Physical AI Project

## 概要

**Version:** 1.3  
**目的:** ローカルLLM（Ollama）を使い、USBカメラ映像・マイク音声・キーボード入力をリアルタイム解析して物理環境とコミュニケーションするAI。Web検索RAGによる最新情報取得・音声出力（TTS）に対応。

## 環境

| 項目 | 内容 |
|------|------|
| GPU | RTX 4070 / VRAM 12GB |
| OS | WSL2 / Ubuntu |
| LLM (テキスト) | Ollama + gemma3:12b |
| LLM (画像) | Ollama + llava:7b |
| 音声認識 | faster-whisper |

## ディレクトリ構成

```
alice/
├── core/
│   ├── vision.py     # OpenCVでUSBカメラ映像取得・llava:7bで解析
│   ├── audio.py      # faster-whisperでマイク音声→テキスト変換
│   ├── llm.py        # Ollama APIでgemma3:12bと会話・検索要否判断
│   ├── search.py     # DuckDuckGo Web/ニュース検索・記事本文取得
│   └── tts.py        # edge-TTSによる日本語音声合成・非同期再生
├── memory/
│   └── db.py         # SQLiteで会話相手プロフィール・会話履歴を記憶
├── main.py           # 音声・映像・キーボード・LLMを統合したメインループ
├── requirements.txt  # 依存ライブラリ
└── CLAUDE.md         # このファイル
```

## 起動方法

```bash
# Ollamaサービス起動（別ターミナル）
ollama serve

# モデルのプリロード（初回）
ollama pull gemma3:12b
ollama pull llava:7b

# Alice起動
python main.py
```

## モジュール説明

### core/vision.py
- USBカメラ（デフォルト `/dev/video0`）からフレームを取得
- フレームをbase64エンコードしてllava:7bに送信
- 視覚情報を自然言語で返す

### core/audio.py
- マイク入力をリアルタイムにキャプチャ（sounddevice）
- faster-whisperで音声→テキスト変換（WSL2対応）
- 起動時にデバイスの有無を確認し、マイクなしでも起動可能（`has_input_device()`）
- マイクが見つからない場合はバックグラウンドスレッドが5秒スリープしてリトライ

### core/llm.py
- Ollama REST API（http://localhost:11434）でgemma3:12bと会話
- 視覚情報・ユーザープロフィール・Web検索結果をシステムプロンプトに組み込む
- ストリーミングレスポンス対応
- `decide_search_query(text)` → `(クエリ, タイプ)` を返す単発判断メソッド（履歴に影響しない）
- 検索タイプ: `"web"`（一般知識）/ `"news"`（ニュース・時事）/ `""`（検索不要）

### core/tts.py
- Microsoft edge-tts（`ja-JP-NanamiNeural`）でテキスト→MP3合成
- miniaudio でMP3デコード → sounddevice で再生（ffmpeg不要）
- `speak(text)` はノンブロッキング：内部キューに積んでワーカースレッドが順次再生
- `clear()` でキューをクリアして再生を即停止（将来の割り込み対応に使用）
- 出力デバイスがない場合は `has_output_device()` が False を返し、`main.py` が TTS を無効化

### core/search.py
- DuckDuckGoで検索（APIキー不要、`ddgs` ライブラリ使用）
- `search_type="web"` → `ddgs.text()` 3件 + 上位1件の記事本文をBeautifulSoupで取得
- `search_type="news"` → `ddgs.news()` 5件（日時・媒体名付き） + 上位2件の本文取得
- ページ取得失敗時はDDGスニペットにフォールバック
- 取得した情報はシステムプロンプトの `【Web検索結果】` セクションに注入

### memory/db.py
- SQLite（`memory/alice.db`）で永続化
- テーブル: `profiles`（会話相手情報）、`conversations`（会話履歴）
- 会話相手の名前・特徴・過去の会話を検索・更新

### main.py（入力フロー）
```
ユーザー入力（音声 or キーボード）
  └→ _fix_surrogates()         # WSL2 stdin のサロゲート文字を修復
  └→ llm.decide_search_query() # LLMが検索要否・クエリ・タイプを判断
        ├ 不要 → そのまま
        └ クエリあり → search_web(query, type) → Web/ニュース検索
  └→ _stream_with_tts()        # LLMトークンを画面表示しながら文末でTTSキューへ送信
        └→ tts.speak(sentence) # 文ごとに非同期で音声再生
```
- 音声とキーボードは `threading.Lock` で直列化（出力の混在を防止）
- キーボード入力: `sys.stdin.buffer` を UTF-8 で明示的に開き直して読み取る
- TTS文区切り文字: `。！？\n`（句点・感嘆符・疑問符・改行）

## 開発メモ

- WSL2ではUSBカメラのパスに注意（`usbipd` でアタッチが必要な場合あり）
- マイク入力はWSL2のPulseAudio/PipeWire経由。未接続でも起動は可能
- Ollamaのモデルは初回起動時にVRAMへロードされる（gemma3:12b + llava:7b で約12GB）
- WSL2 のターミナルで日本語入力すると `\udcXX` サロゲートが混入する場合がある → `_fix_surrogates()` で自動修復
- MSN等のJS重依存サイトはbs4で本文取得できないことがある（スニペットにフォールバック）
- WSL2では音声出力デバイスも未検出になる場合がある → PulseAudio/PipeWire設定で解決。未設定でもテキスト出力で動作継続
- TTS音声は Microsoft Azure 経由（edge-tts）。インターネット接続が必要。完全ローカル化は Style-BERT-VITS2 に移行することで可能
