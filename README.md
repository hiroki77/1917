# 中町兄妹 切り抜き動画自動生成

新着動画を自動検知→切り抜き3本作成→Drive保存。スリープ中も稼働。

## Setup
```bash
git clone https://github.com/hiroki77/1917.git ~/youtube-shorts-automation
cd ~/youtube-shorts-automation && git checkout claude/youtube-shorts-automation-HvDGj
bash automation/termux_setup.sh
echo 'export GEMINI_API_KEY="AIza..."' >> ~/.bashrc && source ~/.bashrc
rclone config  # google drive
python tools/calibrate_colors.py
python main.py --once
bash automation/watch_service.sh
```

## Commands
```bash
bash automation/watch_service.sh start|stop|status|log
python main.py --insights data.json
```
