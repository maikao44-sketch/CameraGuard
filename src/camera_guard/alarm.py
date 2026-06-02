import os
import cv2
import json
import socket
from datetime import datetime
from typing import Dict, Any


class AlarmManager:
    def __init__(self, evidence_dir: str, log_dir: str):
        self.evidence_dir = evidence_dir
        self.log_dir = log_dir
        os.makedirs(self.evidence_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

    def trigger(self, frame, detect_result: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        computer_name = socket.gethostname()

        image_name = f"alarm_{computer_name}_{timestamp}.jpg"
        image_path = os.path.join(self.evidence_dir, image_name)
        cv2.imwrite(image_path, frame)

        event = {
            "event_type": "suspected_phone_recording",
            "event_name": "疑似手机拍摄行为",
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "computer_name": computer_name,
            "evidence_image": image_path,
            "detect_result": detect_result,
        }

        log_path = os.path.join(self.log_dir, "alarm_events.jsonl")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        print(f"[ALARM] 疑似手机拍摄行为，已留证：{image_path}")
        return event
