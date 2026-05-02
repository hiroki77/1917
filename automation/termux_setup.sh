#!/bin/bash
set -e
echo "=== Termux Setup ==="
pkg update -y && pkg install -y python ffmpeg git termux-api rclone
pip install --upgrade pip
pip install yt-dlp schedule pyyaml google-genai openai-whisper easyocr
pip install numpy opencv-python-headless Pillow
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
mkdir -p ~/.termux/boot output temp data fonts logs
cp automation/termux_boot.sh ~/.termux/boot/ && chmod +x ~/.termux/boot/termux_boot.sh
termux-wake-lock; termux-setup-storage
echo ""
echo "Done. Next:"
echo "  1. fonts/ にけいふぉんと.ttf"
echo "  2. echo 'export GEMINI_API_KEY=\"AIza...\"' >> ~/.bashrc && source ~/.bashrc"
echo "  3. rclone config (google drive)"
echo "  4. 設定>アプリ>Termux>バッテリー最適化>無制限"
echo "  5. python tools/calibrate_colors.py"
echo "  6. python main.py --once"
echo "  7. bash automation/watch_service.sh"
