#!/usr/bin/env python3
"""テロップ色キャリブレーションツール
中町兄妹の実動画からテロップ色(RGB/HSV)を自動検出し、
config.yamlを正確に更新する

使い方:
  python tools/calibrate_colors.py
  python tools/calibrate_colors.py --url "https://youtube.com/watch?v=XXXXX"
"""
import os, sys, json, subprocess, argparse, shutil
from pathlib import Path
import numpy as np
try:
    import cv2
except ImportError:
    print("pip install opencv-python-headless"); sys.exit(1)
try:
    import yaml
except ImportError:
    print("pip install pyyaml"); sys.exit(1)

def download_frames(url, temp_dir, count=20):
    os.makedirs(temp_dir, exist_ok=True)
    r = subprocess.run(["yt-dlp", "--print", "duration", "--no-download", url], capture_output=True, text=True, timeout=30)
    dur = float(r.stdout.strip() or 600)
    dl = os.path.join(temp_dir, "sample.mp4")
    subprocess.run(["yt-dlp", "-f", "bestvideo[height<=720]", "--merge-output-format", "mp4", "-o", dl, "--no-playlist", url], capture_output=True, timeout=300)
    r2 = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", dl], capture_output=True, text=True, timeout=10)
    h = 720
    for s in json.loads(r2.stdout)["streams"]:
        if s["codec_type"] == "video": h = s["height"]; break
    sub_h = int(h * 0.20)
    fd = os.path.join(temp_dir, "frames")
    os.makedirs(fd, exist_ok=True)
    iv = (dur * 0.7) / count
    subprocess.run(["ffmpeg", "-y", "-ss", str(dur*0.15), "-i", dl, "-vf", f"fps=1/{iv},crop=iw:{sub_h}:0:{h-sub_h}", "-frames:v", str(count), "-q:v", "2", os.path.join(fd, "f_%03d.jpg")], capture_output=True, timeout=120)
    return sorted(Path(fd).glob("f_*.jpg")), dl

def extract_colors(frames):
    pink, cyan = [], []
    for fp in frames:
        f = cv2.imread(str(fp))
        if f is None: continue
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        mask = (gray > 150) & (hsv[:,:,1] > 40)
        if not np.any(mask): continue
        for i in range(len(hsv[mask])):
            h = hsv[mask][i][0]
            if 140 <= h <= 179 or 0 <= h <= 10:
                pink.append(rgb[mask][i])
            elif 75 <= h <= 105:
                cyan.append(rgb[mask][i])
    return np.array(pink) if pink else np.array([]), np.array(cyan) if cyan else np.array([])

def analyze(pink, cyan):
    res = {}
    for name, px in [("aya", pink), ("junpei", cyan)]:
        if len(px) == 0: continue
        med = np.median(px, axis=0).astype(int)
        res[name] = {"rgb": med.tolist(), "hex": f"{med[0]:02X}{med[1]:02X}{med[2]:02X}", "count": len(px)}
        label = "中町綾(ピンク)" if name == "aya" else "中町純平(シアン)"
        print(f"\n=== {label} ===")
        print(f"  検出: {len(px)} px")
        print(f"  RGB: ({med[0]}, {med[1]}, {med[2]})")
        print(f"  HEX: #{res[name]['hex']}")
    # HSV範囲
    for name, px in [("aya", pink), ("junpei", cyan)]:
        if len(px) == 0: continue
        bgr = px[:,::-1].reshape(-1,1,3).astype(np.uint8)
        hv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).reshape(-1,3)
        r = {"h": [int(np.percentile(hv[:,0],5)), int(np.percentile(hv[:,0],95))],
             "s": [int(np.percentile(hv[:,1],5)), int(np.percentile(hv[:,1],95))],
             "v": [int(np.percentile(hv[:,2],5)), int(np.percentile(hv[:,2],95))]}
        res[name]["hsv_range"] = r
        print(f"  HSV範囲: H={r['h']} S={r['s']} V={r['v']}")
    return res

def update_config(res, path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    changed = False
    if "aya" in res:
        old = cfg["subtitles"]["aya_color"]
        cfg["subtitles"]["aya_color"] = res["aya"]["hex"]
        print(f"\nconfig: aya_color {old} -> {res['aya']['hex']}")
        changed = True
    if "junpei" in res:
        old = cfg["subtitles"]["junpei_color"]
        cfg["subtitles"]["junpei_color"] = res["junpei"]["hex"]
        print(f"config: junpei_color {old} -> {res['junpei']['hex']}")
        changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print("config.yaml 保存完了")

def find_video():
    for cmd in [
        ["yt-dlp", "--flat-playlist", "--print", "%(id)s", "--playlist-items", "1", "https://www.youtube.com/@nakamachi_kyodai/videos"],
        ["yt-dlp", "--flat-playlist", "--print", "%(id)s", "--playlist-items", "1", "ytsearch1:中町兄妹"]
    ]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            v = r.stdout.strip()
            if v: return f"https://www.youtube.com/watch?v={v}"
        except Exception:
            pass
    return None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", type=str)
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--no-update", action="store_true")
    p.add_argument("--frames", type=int, default=20)
    args = p.parse_args()
    td = "./temp/calibration"
    url = args.url or find_video()
    if not url:
        print("動画URLが見つかりません。--urlで指定してください"); sys.exit(1)
    print(f"分析: {url}")
    try:
        frames, _ = download_frames(url, td, args.frames)
        if not frames:
            print("フレーム取得失敗"); sys.exit(1)
        pink, cyan = extract_colors(frames)
        res = analyze(pink, cyan)
        if not args.no_update and res:
            update_config(res, args.config)
        os.makedirs("data", exist_ok=True)
        with open("data/calibration_result.json", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print("\n=== キャリブレーション完了 ===")
    finally:
        shutil.rmtree(td, ignore_errors=True)

if __name__ == "__main__":
    main()
