import os
import shutil
import logging
import subprocess

logger = logging.getLogger(__name__)

class DriveUploader:
    def __init__(self, config):
        dc = config.get("drive", {})
        self.enabled = dc.get("enabled", False)
        self.method = dc.get("method", "rclone")
        self.rclone_remote = dc.get("rclone_remote", "gdrive")
        self.remote_folder = dc.get("remote_folder", "中町兄妹_切り抜き")
        self.shared_path = dc.get("shared_path", "/storage/emulated/0/Movies/切り抜き")

    def upload(self, file_path):
        if not self.enabled or not os.path.exists(file_path):
            return False
        if self.method == "rclone":
            return self._rclone(file_path)
        elif self.method == "shared_storage":
            return self._shared(file_path)
        return False

    def _rclone(self, file_path):
        dest = f"{self.rclone_remote}:{self.remote_folder}/"
        for attempt in range(3):
            try:
                r = subprocess.run(["rclone", "copy", file_path, dest, "--retries", "3"], capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    logger.info(f"Driveアップロード完了: {os.path.basename(file_path)}")
                    return True
                logger.warning(f"rclone error: {r.stderr}")
            except FileNotFoundError:
                logger.error("rclone未インストール: pkg install rclone")
                return False
            except subprocess.TimeoutExpired:
                logger.warning(f"rclone timeout (attempt {attempt+1})")
            import time; time.sleep(5)
        return False

    def _shared(self, file_path):
        try:
            os.makedirs(self.shared_path, exist_ok=True)
            dest = os.path.join(self.shared_path, os.path.basename(file_path))
            shutil.copy2(file_path, dest)
            try:
                subprocess.run(["termux-media-scan", dest], timeout=10)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            logger.info(f"共有ストレージにコピー: {dest}")
            return True
        except Exception as e:
            logger.error(f"コピー失敗: {e}")
            return False
