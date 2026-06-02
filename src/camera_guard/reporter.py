from typing import Dict, Any
import requests


class Reporter:
    def __init__(self, enable: bool, url: str, timeout_seconds: int = 3):
        self.enable = enable
        self.url = url
        self.timeout_seconds = timeout_seconds

    def report(self, event: Dict[str, Any]) -> bool:
        if not self.enable:
            return False
        try:
            response = requests.post(self.url, json=event, timeout=self.timeout_seconds)
            if response.status_code == 200:
                print("[REPORT] 报送成功")
                return True
            print(f"[REPORT] 报送失败：HTTP {response.status_code}")
            return False
        except Exception as exc:
            print(f"[REPORT] 报送异常：{exc}")
            return False
