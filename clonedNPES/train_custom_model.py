"""
ANPR Custom Model Training Script (YOLOv8/v11 via Ultralytics)
Stable and robust version using the installed 'ultralytics' library.
"""

import os
from pathlib import Path
from ultralytics import YOLO

# Configuration
HOME = Path.cwd()
DATASET_DIR = HOME / "training" / "yolov9" / "ANPR2-8"
DATA_YAML = DATASET_DIR / "data.yaml"
MODELS_DIR = HOME / "models"

def check_dataset():
    """Verify dataset exists and paths are correct"""
    print("\n" + "=" * 50)
    print("Checking dataset...")
    
    if not DATA_YAML.exists():
        print(f"❌ Dataset not found at {DATA_YAML}")
        print("Please run setup_training.ps1 first to download it.")
        return False
    
    # Ensure absolute paths in data.yaml
    print("Fixing paths in data.yaml...")
    try:
        with open(DATA_YAML, 'r', encoding='utf-8') as f:
            content = f.read()
            
        import re
        train_path = (DATASET_DIR / "train" / "images").as_posix()
        valid_path = (DATASET_DIR / "valid" / "images").as_posix()
        test_path = (DATASET_DIR / "test" / "images").as_posix()
        
        # Replace paths
        content = re.sub(r'train: .*', f'train: {train_path}', content)
        content = re.sub(r'val: .*', f'val: {valid_path}', content)
        content = re.sub(r'test: .*', f'test: {test_path}', content)
        
        with open(DATA_YAML, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✓ Fixed data.yaml paths (absolute)")
    except Exception as e:
        print(f"⚠️ Could not fix data.yaml: {e}")
        
    print(f"✓ Dataset ready at {DATA_YAML}")
    return True

def train_yolo(epochs=3, img_size=640):
    """Train YOLOv8n model using Ultralytics"""
    print("\n" + "=" * 50)
    print(f"Starting training (Epochs: {epochs})...")
    print("Using Ultralytics YOLOv8 (Stable & Fast)")
    print("=" * 50)
    
    try:
        # Load a pretrained YOLOv8n model
        model = YOLO("yolov8n.pt") 
        
        # Train the model
        # Using CPU-friendly settings
        results = model.train(
            data=str(DATA_YAML),
            epochs=epochs,
            imgsz=img_size,
            plots=True,
            batch=4,          # Low batch size for CPU
            device='cpu',     # Force CPU to avoid CUDA errors if GPU not ready
            workers=2,
            name='anpr_yolov8n_custom',
            exist_ok=True
        )
        
        print("\n✓ Training completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        return False

def integrate_model():
    """Copy best model to application models directory"""
    print("\n" + "=" * 50)
    print("Integrating trained model...")
    
    # Path where ultralytics saves the run
    # Usually runs/detect/anpr_yolov8n_custom/weights/best.pt
    # But updated versions might save in root runs/
    
    possible_paths = [
        HOME / "runs" / "detect" / "anpr_yolov8n_custom" / "weights" / "best.pt",
        HOME / "training" / "ans" / "detect" / "anpr_yolov8n_custom" / "weights" / "best.pt"
    ]
    
    # Find the latest run
    # Ultralytics saves to 'runs' dir in CWD usually
    run_dir = HOME / "runs" / "detect" / "anpr_yolov8n_custom" / "weights" / "best.pt"
    
    if run_dir.exists():
        MODELS_DIR.mkdir(exist_ok=True)
        target = MODELS_DIR / "anpr_custom_best.pt"
        
        import shutil
        shutil.copy2(run_dir, target)
        print(f"✓ Model integrated to: {target}")
        print("The application will now use this custom model automatically.")
        return True
    
    print(f"❌ Could not find trained model at {run_dir}")
    return False

def main():
    if not check_dataset():
        return
        
    # epochs=3 for fast validation. Change to 50 for better accuracy.
    if train_yolo(epochs=3):
        integrate_model()

if __name__ == "__main__":
    main()
