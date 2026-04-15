#!/bin/bash
set -e
echo "=== Termux Setup ==="
pkg update -y && pkg install -y python ffmpeg git termux-api
pip install --upgrade pip
pip install yt-dlp feedparser schedule pyyaml openai-whisper easyocr numpy opencv-python-headless Pillow
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
mkdir -p ~/.termux/boot output temp data fonts logs
cp automation/termux_boot.sh ~/.termux/boot/ && chmod +x ~/.termux/boot/termux_boot.sh
termux-wake-lock
echo "Done. Put keifont.ttf in fonts/ then run: python main.py"
