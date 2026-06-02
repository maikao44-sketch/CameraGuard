from typing import Dict, List, Any
from ultralytics import YOLO


class PhoneDetector:
    def __init__(self, model_path: str, confidence: float = 0.35):
        self.model = YOLO(model_path)
        self.confidence = confidence

    def detect(self, frame) -> Dict[str, Any]:
        results = self.model(frame, verbose=False)
        persons: List[Dict[str, Any]] = []
        phones: List[Dict[str, Any]] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                name = self.model.names.get(cls_id, str(cls_id))
                if conf < self.confidence:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                item = {
                    "class": name,
                    "confidence": round(conf, 4),
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                }

                if name == "person":
                    persons.append(item)
                elif name == "cell phone":
                    phones.append(item)

        return {
            "has_person": len(persons) > 0,
            "has_phone": len(phones) > 0,
            "persons": persons,
            "phones": phones,
        }
