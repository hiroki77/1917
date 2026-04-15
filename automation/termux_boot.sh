#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd "$HOME/youtube-shorts-automation" || exit 1
nohup python main.py >> logs/automation.log 2>&1 &
termux-notification --title "切り抜き自動生成" --content "監視開始"
