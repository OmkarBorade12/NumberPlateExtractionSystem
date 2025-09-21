import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import cv2
import easyocr
from ultralytics import YOLO
import csv
import os
import pandas as pd
from PIL import Image, ImageTk
from plate_utils import initialize_plate_cache, save_plate_to_csv

running = False
reader = easyocr.Reader(['en'])
model = YOLO('yolov8n.pt')

def detect_plates():
    global running
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        messagebox.showerror("Error", "Camera not accessible")
        return

    while running:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue  # Skip if frame is invalid

        results = model(frame)
        boxes = results[0].boxes.xyxy.cpu().numpy()

        if len(boxes) == 0:
            print("No objects detected")
            continue

        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            plate_img = frame[y1:y2, x1:x2]

            if plate_img.size == 0:
                print("Empty plate image")
                continue

            text = reader.readtext(plate_img)
            if not text:
                print("No text detected")
                continue

            for (_, txt, prob) in text:
                print(f"Detected: {txt} with confidence {prob}")
                save_plate_to_csv(txt, prob, plate_img=plate_img)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, txt, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

        cv2.imshow("Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

def start_detection():
    global running
    if not running:
        running = True
        threading.Thread(target=detect_plates).start()

def stop_detection():
    global running
    running = False

def enlarge_image(path):
    top = tk.Toplevel()
    top.title("Full Image")
    try:
        img = Image.open(path)
        photo = ImageTk.PhotoImage(img)
        label = tk.Label(top, image=photo)
        label.image = photo
        label.pack()
    except:
        tk.Label(top, text="Image not found").pack()

def show_csv_data(filtered_rows=None):
    try:
        with open('detected_plates.csv', newline='') as file:
            reader = csv.reader(file)
            headers = next(reader, None)
            if headers is None:
                headers = ['Plate Text', 'Date', 'Time', 'Image Path']

            raw_rows = filtered_rows if filtered_rows else list(reader)
            rows = []
            for row in raw_rows:
                # support old 3-col and older 5-col formats; prefer 4-col (Plate,Date,Time,Image)
                if len(row) == 3:
                    plate, date, time = row
                    img_path = ''
                    rows.append([plate, date, time, img_path])
                elif len(row) == 4:
                    rows.append(row)
                elif len(row) == 5:
                    # legacy with Count present - drop the Count column
                    plate, date, time, _count, img_path = row
                    rows.append([plate, date, time, img_path])
                else:
                    continue  # skip invalid rows

            if not rows:
                messagebox.showinfo("Info", "No plates detected yet.")
                return

            top = tk.Toplevel()
            top.title("Detected Plates")

            canvas = tk.Canvas(top)
            scrollbar = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
            scroll_frame = ttk.Frame(canvas)

            scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Ensure headers reflect current format (no Count)
            cur_headers = ['Plate Text', 'Date', 'Time', 'Image Path']
            for i, header in enumerate(cur_headers):
                label = ttk.Label(scroll_frame, text=header, font=('Arial', 10, 'bold'), borderwidth=1, relief="solid", width=20)
                label.grid(row=0, column=i)

            image_refs = []

            for r, row in enumerate(rows, start=1):
                for c, value in enumerate(row):
                    # image is last column (index 3)
                    if c == 3 and value and os.path.exists(value):
                        try:
                            img = Image.open(value)
                            img.thumbnail((100, 40))
                            photo = ImageTk.PhotoImage(img)
                            image_refs.append(photo)
                            label = tk.Label(scroll_frame, image=photo, borderwidth=1, relief="solid", cursor="hand2")
                            label.bind("<Button-1>", lambda e, p=value: enlarge_image(p))
                        except:
                            label = ttk.Label(scroll_frame, text="Image not found", borderwidth=1, relief="solid")
                    else:
                        label = ttk.Label(scroll_frame, text=value, borderwidth=1, relief="solid", width=20)
                    label.grid(row=r, column=c)

    except FileNotFoundError:
        messagebox.showinfo("Info", "CSV file not found.")

def filter_data():
    plate_query = plate_entry.get().strip().upper()
    date_query = date_entry.get().strip()
    filtered = []
    try:
        with open('detected_plates.csv', newline='') as file:
            reader = csv.reader(file)
            headers = next(reader, None)
            raw_rows = list(reader)
            for row in raw_rows:
                if len(row) == 3:
                    plate, date, time = row
                    count = '1'
                    img_path = ''
                    processed_row = [plate, date, time, count, img_path]
                elif len(row) == 5:
                    processed_row = row
                else:
                    continue
                plate, date, time, count, img_path = processed_row
                if (plate_query in plate) and (date_query in date):
                    filtered.append(processed_row)
        show_csv_data(filtered)
    except FileNotFoundError:
        messagebox.showinfo("Info", "CSV file not found.")

def export_to_excel():
    try:
        df = pd.read_csv('detected_plates.csv')
        filepath = filedialog.asksaveasfilename(defaultextension=".xlsx")
        if filepath:
            df.to_excel(filepath, index=False)
            messagebox.showinfo("Success", f"Exported to {filepath}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# GUI Setup
initialize_plate_cache()
root = tk.Tk()
root.title("Number Plate Detection")

ttk.Button(root, text="Start Detection", command=start_detection).pack(pady=5)
ttk.Button(root, text="Stop Detection", command=stop_detection).pack(pady=5)
ttk.Button(root, text="View All Plates", command=show_csv_data).pack(pady=5)

ttk.Label(root, text="Search by Plate:").pack()
plate_entry = ttk.Entry(root)
plate_entry.pack()

ttk.Label(root, text="Search by Date (YYYY-MM-DD):").pack()
date_entry = ttk.Entry(root)
date_entry.pack()

ttk.Button(root, text="Filter Results", command=filter_data).pack(pady=5)
ttk.Button(root, text="Export to Excel", command=export_to_excel).pack(pady=5)

root.mainloop()