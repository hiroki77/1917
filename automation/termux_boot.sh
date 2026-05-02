#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd "$HOME/youtube-shorts-automation" || exit 1
if [ -f /tmp/yt_auto.pid ] && kill -0 "$(cat /tmp/yt_auto.pid)" 2>/dev/null; then exit 0; fi
nohup python watchdog.py >> logs/watchdog.log 2>&1 &
echo $! > /tmp/yt_auto.pid
termux-notification --title "切り抜き自動生成" --content "監視開始(クラッシュ自動復帰)" --ongoing --id yt_auto
