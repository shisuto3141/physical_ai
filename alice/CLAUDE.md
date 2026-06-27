# Alice — Physical AI Project

## 概要

**Version:** 1.0  
**目的:** ローカルLLM（Ollama）を使い、USBカメラ映像・マイク音声をリアルタイム解析して物理環境とコミュニケーションするAI

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
│   └── llm.py        # Ollama APIでgemma3:12bと会話
├── memory/
│   └── db.py         # SQLiteで会話相手プロフィール・会話履歴を記憶
├── main.py           # 音声・映像・LLMを統合したメインループ
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
- マイク入力をリアルタイムにキャプチャ（PyAudio）
- faster-whisperで音声→テキスト変換（WSL2対応）
- VAD（Voice Activity Detection）で発話区間を検出

### core/llm.py
- Ollama REST API（http://localhost:11434）でgemma3:12bと会話
- 視覚情報・会話履歴・ユーザープロフィールをコンテキストに組み込む
- ストリーミングレスポンス対応

### memory/db.py
- SQLite（`memory/alice.db`）で永続化
- テーブル: `profiles`（会話相手情報）、`conversations`（会話履歴）
- 会話相手の名前・特徴・過去の会話を検索・更新

## 開発メモ

- WSL2ではUSBカメラのパスに注意（`usbipd` でアタッチが必要な場合あり）
- マイク入力はWSL2のPulseAudio経由
- Ollamaのモデルは初回起動時にVRAMへロードされる（gemma3:12b + llava:7b で約12GB）
