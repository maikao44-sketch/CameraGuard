from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np


PERSON_CLASS_ID = 0
PHONE_CLASS_ID = 67
CLASS_NAMES = {
    PERSON_CLASS_ID: "person",
    PHONE_CLASS_ID: "cell phone",
}


class PhoneDetector:
    def __init__(
        self,
        model_path: str,
        confidence: float = 0.35,
        backend: str = "onnx",
        iou_threshold: float = 0.45,
        imgsz: Any = None,
    ):
        self.backend = (backend or "onnx").lower().strip()
        self.confidence = confidence
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz

        if self.backend == "onnx":
            self._init_onnx(model_path)
        else:
            self._init_ultralytics(model_path)

    def _init_ultralytics(self, model_path: str) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_path)

    def _init_onnx(self, model_path: str) -> None:
        import onnxruntime as ort

        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = self._resolve_input_size(self.session.get_inputs()[0].shape)

    def _resolve_input_size(self, input_shape: Sequence[Any]) -> Tuple[int, int]:
        configured = self._parse_imgsz(self.imgsz)
        if configured:
            return configured

        if len(input_shape) >= 4:
            shape_h, shape_w = input_shape[2], input_shape[3]
            if isinstance(shape_h, int) and isinstance(shape_w, int) and shape_h > 0 and shape_w > 0:
                return int(shape_w), int(shape_h)

        return 640, 640

    def _parse_imgsz(self, imgsz: Any) -> Optional[Tuple[int, int]]:
        if imgsz is None:
            return None
        if isinstance(imgsz, int):
            return int(imgsz), int(imgsz)
        if isinstance(imgsz, str):
            text = imgsz.lower().replace("x", ",")
            parts = [part.strip() for part in text.split(",") if part.strip()]
            if len(parts) == 1 and parts[0].isdigit():
                size = int(parts[0])
                return size, size
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                return int(parts[0]), int(parts[1])
        if isinstance(imgsz, (list, tuple)) and len(imgsz) >= 2:
            return int(imgsz[0]), int(imgsz[1])
        return None

    def detect(self, frame) -> Dict[str, Any]:
        if self.backend == "onnx":
            return self._detect_onnx(frame)
        return self._detect_ultralytics(frame)

    def _detect_ultralytics(self, frame) -> Dict[str, Any]:
        results = self.model(frame, verbose=False)
        persons: List[Dict[str, Any]] = []
        phones: List[Dict[str, Any]] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id not in CLASS_NAMES:
                    continue

                conf = float(box.conf[0])
                if conf < self.confidence:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                item = {
                    "class": CLASS_NAMES[cls_id],
                    "confidence": round(conf, 4),
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                }

                if cls_id == PERSON_CLASS_ID:
                    persons.append(item)
                elif cls_id == PHONE_CLASS_ID:
                    phones.append(item)

        return self._format_result(persons, phones)

    def _detect_onnx(self, frame) -> Dict[str, Any]:
        input_tensor, ratio, pad = self._preprocess(frame)
        outputs = self.session.run(None, {self.input_name: input_tensor})
        detections = self._extract_detections(outputs[0])

        boxes: List[List[float]] = []
        scores: List[float] = []
        class_ids: List[int] = []

        for det in detections:
            parsed = self._parse_detection(det)
            if parsed is None:
                continue
            box, score, class_id = parsed
            if class_id not in CLASS_NAMES or score < self.confidence:
                continue
            boxes.append(box)
            scores.append(score)
            class_ids.append(class_id)

        keep = self._nms(boxes, scores, class_ids)
        persons: List[Dict[str, Any]] = []
        phones: List[Dict[str, Any]] = []
        frame_h, frame_w = frame.shape[:2]

        for idx in keep:
            x1, y1, x2, y2 = self._scale_box(boxes[idx], ratio, pad, frame_w, frame_h)
            class_id = class_ids[idx]
            item = {
                "class": CLASS_NAMES[class_id],
                "confidence": round(float(scores[idx]), 4),
                "box": [int(x1), int(y1), int(x2), int(y2)],
            }
            if class_id == PERSON_CLASS_ID:
                persons.append(item)
            elif class_id == PHONE_CLASS_ID:
                phones.append(item)

        return self._format_result(persons, phones)

    def _preprocess(self, frame):
        input_w, input_h = self.input_size
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized, ratio, pad = self._letterbox(rgb, input_w, input_h)
        image = resized.astype(np.float32) / 255.0
        image = np.transpose(image, (2, 0, 1))[None, ...]
        return np.ascontiguousarray(image), ratio, pad

    def _letterbox(self, image, input_w: int, input_h: int):
        src_h, src_w = image.shape[:2]
        ratio = min(input_w / src_w, input_h / src_h)
        new_w, new_h = int(round(src_w * ratio)), int(round(src_h * ratio))
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        pad_w = input_w - new_w
        pad_h = input_h - new_h
        left = pad_w // 2
        right = pad_w - left
        top = pad_h // 2
        bottom = pad_h - top
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        return padded, ratio, (left, top)

    def _extract_detections(self, output) -> np.ndarray:
        output = np.squeeze(output)
        if output.ndim == 1:
            output = output[None, :]
        if output.ndim == 2 and output.shape[0] < output.shape[1] and output.shape[0] in (84, 85):
            output = output.T
        return output

    def _parse_detection(self, det):
        if len(det) < 6:
            return None

        cx, cy, w, h = [float(v) for v in det[:4]]
        class_scores = det[4:]
        if len(det) >= 85:
            objectness = float(det[4])
            class_scores = det[5:]
        else:
            objectness = 1.0

        wanted_scores = {
            PERSON_CLASS_ID: float(class_scores[PERSON_CLASS_ID]) if len(class_scores) > PERSON_CLASS_ID else 0.0,
            PHONE_CLASS_ID: float(class_scores[PHONE_CLASS_ID]) if len(class_scores) > PHONE_CLASS_ID else 0.0,
        }
        class_id = max(wanted_scores, key=wanted_scores.get)
        score = objectness * wanted_scores[class_id]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2
        return [x1, y1, x2, y2], score, class_id

    def _nms(self, boxes: List[List[float]], scores: List[float], class_ids: List[int]) -> List[int]:
        keep: List[int] = []
        for class_id in CLASS_NAMES:
            idxs = [idx for idx, value in enumerate(class_ids) if value == class_id]
            if not idxs:
                continue

            class_boxes = [[boxes[idx][0], boxes[idx][1], boxes[idx][2] - boxes[idx][0], boxes[idx][3] - boxes[idx][1]] for idx in idxs]
            class_scores = [scores[idx] for idx in idxs]
            selected = cv2.dnn.NMSBoxes(class_boxes, class_scores, self.confidence, self.iou_threshold)
            if len(selected) == 0:
                continue
            for selected_idx in np.array(selected).flatten():
                keep.append(idxs[int(selected_idx)])
        return keep

    def _scale_box(self, box, ratio: float, pad: Tuple[int, int], frame_w: int, frame_h: int):
        left, top = pad
        x1 = (box[0] - left) / ratio
        y1 = (box[1] - top) / ratio
        x2 = (box[2] - left) / ratio
        y2 = (box[3] - top) / ratio
        x1 = max(0, min(frame_w - 1, x1))
        y1 = max(0, min(frame_h - 1, y1))
        x2 = max(0, min(frame_w - 1, x2))
        y2 = max(0, min(frame_h - 1, y2))
        return x1, y1, x2, y2

    def _format_result(self, persons: List[Dict[str, Any]], phones: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "has_person": len(persons) > 0,
            "has_phone": len(phones) > 0,
            "persons": persons,
            "phones": phones,
        }
