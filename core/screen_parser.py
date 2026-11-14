import base64
import io
import time
import requests
import yaml
import urllib3
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ScreenParser:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = str(BASE_DIR / "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.api_url = config["omniparser"]["api_url"]
        self.screen_width = config.get("screen", {}).get("width", 1920)
        self.screen_height = config.get("screen", {}).get("height", 1080)

    def parse(self, screenshot_bytes):
        # 缩小截图，减少传输
        img = Image.open(io.BytesIO(screenshot_bytes))
        img.thumbnail((800, 450))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        screenshot_bytes = buf.getvalue()

        img_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    f"{self.api_url.rstrip('/')}/parse",
                    json={"image_base64": img_b64},
                    verify=False,
                    timeout=60
                )
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}")

                output = response.json()

                # 兼容 list 和 dict
                if isinstance(output, list) and len(output) >= 2:
                    elements_raw = output[1]
                elif isinstance(output, list):
                    elements_raw = output
                elif isinstance(output, dict) and "elements" in output:
                    elements_raw = output["elements"]
                else:
                    elements_raw = []

                if not isinstance(elements_raw, list):
                    raise Exception("元素列表不是 list")

                elements = []
                for item in elements_raw:
                    if not isinstance(item, dict):
                        continue
                    bbox_norm = item.get("bbox", [0, 0, 0, 0])
                    abs_bbox = [
                        int(bbox_norm[0] * self.screen_width),
                        int(bbox_norm[1] * self.screen_height),
                        int(bbox_norm[2] * self.screen_width),
                        int(bbox_norm[3] * self.screen_height)
                    ]
                    elements.append({
                        "type": item.get("type", "icon"),
                        "content": item.get("content", ""),
                        "interactivity": item.get("interactivity", False),
                        "bbox": abs_bbox
                    })
                return elements

            except Exception as e:
                print(f"⚠️ 第{attempt}次请求失败: {e}")
                if attempt == max_attempts:
                    raise
                print("🔄 2秒后重试...")
                time.sleep(2)