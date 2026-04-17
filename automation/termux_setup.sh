#!/bin/bash
set -e
echo "=== Termux Setup ==="
pkg update -y && pkg install -y python ffmpeg git termux-api rclone
pip install --upgrade pip
pip install yt-dlp feedparser schedule pyyaml google-genai openai-whisper easyocr numpy opencv-python-headless Pillow
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
mkdir -p ~/.termux/boot output temp data fonts logs
cp automation/termux_boot.sh ~/.termux/boot/ && chmod +x ~/.termux/boot/termux_boot.sh
termux-wake-lock
termux-setup-storage
echo "\n=== Done ==="
echo "1. fonts/ にけいふぉんと.ttfを配置"
echo "2. config.yaml にGemini APIキー設定 (https://aistudio.google.com/apikey)"
echo "3. rclone config でGoogle Drive設定"
echo "4. 設定>アプリ>Termux>バッテリー最適化>無制限"
echo "5. python main.py --once でテスト"
