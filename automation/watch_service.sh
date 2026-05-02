#!/bin/bash
PD="$(cd "$(dirname "$0")/.." && pwd)";cd "$PD"
case "${1:-start}" in
  start)
    if [ -f /tmp/yt_auto.pid ] && kill -0 "$(cat /tmp/yt_auto.pid)" 2>/dev/null; then echo "実行中(PID:$(cat /tmp/yt_auto.pid))";exit 0;fi
    termux-wake-lock 2>/dev/null||true;nohup python watchdog.py>>logs/watchdog.log 2>&1 &
    echo $!>/tmp/yt_auto.pid;echo "開始(PID:$(cat /tmp/yt_auto.pid)) log: bash $0 log";;
  stop) [ -f /tmp/yt_auto.pid ]&&{PID=$(cat /tmp/yt_auto.pid);kill $PID 2>/dev/null;pkill -P $PID 2>/dev/null;rm -f /tmp/yt_auto.pid;echo "停止";}||echo "なし";termux-wake-unlock 2>/dev/null||true;;
  status) [ -f /tmp/yt_auto.pid ]&&kill -0 "$(cat /tmp/yt_auto.pid)" 2>/dev/null&&{echo "実行中(PID:$(cat /tmp/yt_auto.pid))";tail -5 logs/automation.log 2>/dev/null;}||echo "停止中";;
  log) tail -f logs/automation.log;;
  *) echo "Usage: $0 {start|stop|status|log}";;
esac
