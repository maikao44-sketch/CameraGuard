from math import hypot
from typing import Dict, Any, Tuple


def _center(box):
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, (y1 + y2) / 2


def _overlap_area(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    overlap_x = max(0, min(ax2, bx2) - max(ax1, bx1))
    overlap_y = max(0, min(ay2, by2) - max(ay1, by1))
    return overlap_x * overlap_y


def is_suspicious_phone_recording(result: Dict[str, Any], frame_size: Tuple[int, int], rule_cfg: Dict[str, Any]) -> bool:
    width, height = frame_size
    if not result.get("has_person") or not result.get("has_phone"):
        return False

    cx_min = width * float(rule_cfg.get("center_x_min_ratio", 0.25))
    cx_max = width * float(rule_cfg.get("center_x_max_ratio", 0.75))
    cy_min = height * float(rule_cfg.get("center_y_min_ratio", 0.15))
    cy_max = height * float(rule_cfg.get("center_y_max_ratio", 0.85))
    distance_threshold = hypot(width, height) * float(rule_cfg.get("phone_person_distance_ratio", 0.18))

    for phone in result["phones"]:
        pbox = phone["box"]
        pcx, pcy = _center(pbox)
        in_center_area = cx_min <= pcx <= cx_max and cy_min <= pcy <= cy_max

        for person in result["persons"]:
            bbox = person["box"]
            if _overlap_area(pbox, bbox) > 0:
                return True
            bcx, bcy = _center(bbox)
            near_person = hypot(pcx - bcx, pcy - bcy) <= distance_threshold
            if in_center_area and near_person:
                return True

        if in_center_area:
            return True

    return False
