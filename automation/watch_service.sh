#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
if [ -f /tmp/yt_auto.pid ] && kill -0 $(cat /tmp/yt_auto.pid) 2>/dev/null; then
    echo "Already running (PID: $(cat /tmp/yt_auto.pid))"
    exit 1
fi
termux-wake-lock 2>/dev/null || true
nohup python main.py >> logs/automation.log 2>&1 &
echo $! > /tmp/yt_auto.pid
echo "Started (PID: $(cat /tmp/yt_auto.pid)). Log: tail -f logs/automation.log"
