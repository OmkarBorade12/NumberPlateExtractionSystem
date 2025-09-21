import cv2
import os
import csv
from datetime import datetime
import easyocr
from ultralytics import YOLO
from plate_utils import save_plate_to_csv, normalize_plate, is_valid_plate

model = YOLO('yolov8n.pt')  # Make sure this file exists
reader = easyocr.Reader(['en'])
cap = cv2.VideoCapture(0)  # Use 0 for webcam

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame)
    boxes = results[0].boxes.xyxy.cpu().numpy()

    for box in boxes:
        x1, y1, x2, y2 = map(int, box)
        plate_img = frame[y1:y2, x1:x2]
        text = reader.readtext(plate_img)

        for (bbox, txt, prob) in text:
            # pass confidence (prob) to the helper in plate_utils
            try:
                save_plate_to_csv(txt, prob, plate_img=plate_img)
            except Exception:
                # fallback: call with text and prob only
                try:
                    save_plate_to_csv(txt, prob)
                except Exception:
                    pass

    # Fallback: if YOLO did not find plates (or detections did not pass), try OCR over the full frame
    if len(boxes) == 0:
        try:
            texts = reader.readtext(frame)
            for (bbox, txt, prob) in texts:
                if prob < 0.4:
                    continue
                normalized = normalize_plate(txt)
                if is_valid_plate(normalized):
                    # crop the bbox from the frame
                    try:
                        x_coords = [int(p[0]) for p in bbox]
                        y_coords = [int(p[1]) for p in bbox]
                        x_min, x_max = max(0, min(x_coords)), min(frame.shape[1], max(x_coords))
                        y_min, y_max = max(0, min(y_coords)), min(frame.shape[0], max(y_coords))
                        crop = frame[y_min:y_max, x_min:x_max]
                    except Exception:
                        crop = frame.copy()
                    save_plate_to_csv(normalized, prob, plate_img=crop)
        except Exception:
            pass
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, txt, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

    cv2.imshow("Number Plate Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()