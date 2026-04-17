#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
PROJECT_DIR="$HOME/youtube-shorts-automation"
cd "$PROJECT_DIR" || exit 1
if [ -f /tmp/yt_auto.pid ] && kill -0 "$(cat /tmp/yt_auto.pid)" 2>/dev/null; then
    exit 0
fi
nohup python main.py >> logs/automation.log 2>&1 &
echo $! > /tmp/yt_auto.pid
termux-notification --title "切り抜き自動生成" --content "中町兄妹監視開始" --ongoing --id "yt_auto"
