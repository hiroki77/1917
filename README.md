# 中町兄妹 切り抜き動画自動生成

新着動画を自動検知 → Gemini 2.0 Flash(無料)でテロップOCR → 3本切り抜き自動作成 → Google Driveに保存

## セットアップ
```bash
git clone https://github.com/hiroki77/1917.git ~/youtube-shorts-automation
cd ~/youtube-shorts-automation && git checkout claude/youtube-shorts-automation-HvDGj
bash automation/termux_setup.sh
# fonts/にけいふぉんと.ttfを配置
# config.yamlにGemini APIキー設定
python main.py --once  # テスト
bash automation/watch_service.sh  # 自動監視開始
```
