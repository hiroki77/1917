#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
case "${1:-start}" in
  start)
    if [ -f /tmp/yt_auto.pid ] && kill -0 "$(cat /tmp/yt_auto.pid)" 2>/dev/null; then
      echo "実行中 (PID: $(cat /tmp/yt_auto.pid))"; exit 0; fi
    termux-wake-lock 2>/dev/null || true
    nohup python main.py >> logs/automation.log 2>&1 &
    echo $! > /tmp/yt_auto.pid
    echo "開始 (PID: $(cat /tmp/yt_auto.pid))";;
  stop)
    [ -f /tmp/yt_auto.pid ] && kill "$(cat /tmp/yt_auto.pid)" 2>/dev/null && rm -f /tmp/yt_auto.pid && echo "停止"
    termux-wake-unlock 2>/dev/null || true;;
  status)
    [ -f /tmp/yt_auto.pid ] && kill -0 "$(cat /tmp/yt_auto.pid)" 2>/dev/null && echo "実行中" || echo "停止中";;
esac
