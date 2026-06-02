import os
import yaml
from dataclasses import dataclass
from typing import Any, Dict, Union


@dataclass
class AppConfig:
    raw: Dict[str, Any]

    @property
    def camera_index(self) -> Union[int, str]:
        value = self.raw.get("camera", {}).get("index", "auto")
        if isinstance(value, str) and value.lower().strip() in ("auto", "front", "default"):
            return "auto"
        return int(value)

    @property
    def camera_prefer_front(self) -> bool:
        return bool(self.raw.get("camera", {}).get("prefer_front", True))

    @property
    def camera_probe_max_index(self) -> int:
        return int(self.raw.get("camera", {}).get("probe_max_index", 5))

    @property
    def camera_width(self) -> int:
        return int(self.raw.get("camera", {}).get("width", 1280))

    @property
    def camera_height(self) -> int:
        return int(self.raw.get("camera", {}).get("height", 720))

    @property
    def show_window(self) -> bool:
        return bool(self.raw.get("camera", {}).get("show_window", True))

    @property
    def model_path(self) -> str:
        return str(self.raw.get("model", {}).get("path", "yolov8n.onnx"))

    @property
    def model_backend(self) -> str:
        model = self.raw.get("model", {})
        backend = model.get("backend")
        if backend:
            return str(backend).lower().strip()
        return "onnx" if self.model_path.lower().endswith(".onnx") else "ultralytics"

    @property
    def model_confidence(self) -> float:
        return float(self.raw.get("model", {}).get("confidence", 0.35))

    @property
    def model_iou_threshold(self) -> float:
        return float(self.raw.get("model", {}).get("iou_threshold", 0.45))

    @property
    def model_imgsz(self):
        return self.raw.get("model", {}).get("imgsz")

    @property
    def target_fps(self) -> float:
        return max(1.0, float(self.raw.get("performance", {}).get("target_fps", 10)))

    @property
    def detect_every_n_frames(self) -> int:
        return max(1, int(self.raw.get("performance", {}).get("detect_every_n_frames", 3)))

    @property
    def ui_update_interval_ms(self) -> int:
        return max(16, int(self.raw.get("performance", {}).get("ui_update_interval_ms", 80)))

    @property
    def suspicious_frame_threshold(self) -> int:
        return int(self.raw.get("alarm", {}).get("suspicious_frame_threshold", 20))

    @property
    def cooldown_seconds(self) -> int:
        return int(self.raw.get("alarm", {}).get("cooldown_seconds", 10))

    @property
    def evidence_dir(self) -> str:
        return str(self.raw.get("alarm", {}).get("evidence_dir", "evidence"))

    @property
    def log_dir(self) -> str:
        return str(self.raw.get("alarm", {}).get("log_dir", "logs"))

    @property
    def save_annotated_image(self) -> bool:
        return bool(self.raw.get("alarm", {}).get("save_annotated_image", True))

    @property
    def lock_screen_enable(self) -> bool:
        return bool(self.raw.get("lock_screen", {}).get("enable", False))

    @property
    def lock_screen_delay_seconds(self) -> float:
        return float(self.raw.get("lock_screen", {}).get("delay_seconds", 0))

    @property
    def report_enable(self) -> bool:
        return bool(self.raw.get("report", {}).get("enable", False))

    @property
    def report_url(self) -> str:
        return str(self.raw.get("report", {}).get("url", ""))

    @property
    def report_timeout_seconds(self) -> int:
        return int(self.raw.get("report", {}).get("timeout_seconds", 3))


def load_config(path: str = "config.yaml") -> AppConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AppConfig(data)
