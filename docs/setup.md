# Physical AI — 環境構築・起動手順

最終更新: 2026-06-27

---

## 全体構成

```
physical_ai/
├── alice/          # メインAIシステム（音声・映像・LLM統合）
├── ollama/         # OllamaをDockerで動かすための設定
│   ├── docker-compose.yml
│   └── start.sh
└── docs/           # このディレクトリ（マニュアル・開発ログ）
    └── setup.md
```

---

## 1. 前提条件

### ハードウェア
| 項目 | 内容 |
|------|------|
| GPU | RTX 4070 (VRAM 12GB) |
| OS | WSL2 / Ubuntu |

### ソフトウェア（初回のみセットアップ）

#### Docker のインストール
```bash
# 公式スクリプトでインストール
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# ログアウト→ログインで反映
```

#### NVIDIA Container Toolkit のインストール
Dockerコンテナ内からGPUを使うために必要。

```bash
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

#### Python依存ライブラリ（Alice用）
```bash
# PortAudioのシステムパッケージ（PyAudio のビルドに必要）
sudo apt install -y portaudio19-dev

# Pythonライブラリ
cd /home/shisuto/physical_ai/alice
pip install -r requirements.txt
```

---

## 2. Ollama の起動（Docker）

### 通常起動
```bash
cd /home/shisuto/physical_ai/ollama
./start.sh
```

`start.sh` は以下を自動で行う：
1. Dockerコンテナをバックグラウンドで起動
2. Ollama APIが応答するまで待機
3. `gemma3:12b` と `llava:7b` が未取得なら自動でpull

### 停止
```bash
cd /home/shisuto/physical_ai/ollama
docker compose down
```

### 状態確認
```bash
# コンテナの稼働確認
docker compose ps

# ログのリアルタイム表示
docker compose logs -f

# API疎通確認
curl http://localhost:11434
# → "Ollama is running" と返ればOK
```

### モデルの手動pull（必要な場合）
```bash
docker exec ollama ollama pull gemma3:12b
docker exec ollama ollama pull llava:7b
```

### モデル一覧の確認
```bash
docker exec ollama ollama list
```

---

## 3. Alice の起動

Ollamaが起動済みであることを確認してから実行する。

```bash
cd /home/shisuto/physical_ai/alice
python main.py
```

---

## 4. トラブルシューティング

### `portaudio.h: No such file or directory`（PyAudioビルドエラー）
```bash
sudo apt install -y portaudio19-dev
pip install -r requirements.txt
```

### Dockerコンテナ内からGPUが見えない
```bash
# GPUが認識されているか確認
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu20.04 nvidia-smi
```
→ エラーが出る場合は nvidia-container-toolkit の再インストールを試す。

### WSL2再起動後にOllamaが繋がらない
Windows再起動後はDockerサービスも止まるため、再度 `./start.sh` を実行する。

### USBカメラが認識されない（Alice）
WSL2ではUSBデバイスを手動でアタッチする必要がある（Windows側で実行）：
```powershell
# PowerShell（管理者）で実行
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

---

## 5. ポート一覧

| サービス | ポート | 用途 |
|----------|--------|------|
| Ollama API | 11434 | LLM推論エンドポイント |

---

## 関連ドキュメント

- [Alice CLAUDE.md](../alice/CLAUDE.md) — Aliceモジュール仕様
