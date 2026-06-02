import cv2


def draw_detection(frame, result, suspicious=False):
    for person in result.get("persons", []):
        x1, y1, x2, y2 = person["box"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 180, 0), 2)
        cv2.putText(frame, f"person {person['confidence']:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 0), 2)

    for phone in result.get("phones", []):
        x1, y1, x2, y2 = phone["box"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 220), 2)
        cv2.putText(frame, f"cell phone {phone['confidence']:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 220), 2)

    if suspicious:
        cv2.putText(frame, "SUSPECTED PHONE RECORDING", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
