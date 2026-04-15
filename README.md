# 中町兄妹 切り抜き動画自動生成

新着動画を自動検知し、3本の切り抜き(20-60秒)を自動作成。スマホスリープ時も動作。

## セットアップ
```bash
git clone https://github.com/hiroki77/1917.git ~/youtube-shorts-automation
cd ~/youtube-shorts-automation
git checkout claude/youtube-shorts-automation-HvDGj
bash automation/termux_setup.sh
# fonts/にけいふぉんと.ttfを配置
python main.py --once  # テスト
bash automation/watch_service.sh  # 自動監視開始
```

## インサイト反映
```bash
python main.py --insights insights.json
```
