# Metin Color Detector

Detects Metin stones on the screen using OCR. When debug mode is enabled, the script saves screenshots every 10 seconds with red circles and labels for detected Metins.

## What it does
- Captures the entire screen.
- Detects Metin stones by recognizing the word `Metinul` via OCR.
- Prints detected Metin type and center coordinates.
- In debug mode, saves annotated screenshots in the `debug/` folder.

## Configuration
Open `main.py` and adjust:
- `DETECTION_ENABLED` – enable/disable detection
- `DEBUG_MODE` – enable/disable debug screenshots
- `DEBUG_INTERVAL_SEC` – interval between debug screenshots
- `CAPTURE_INTERVAL_SEC` – capture loop delay
- `MIN_CONTOUR_AREA` – minimum blob size
- `OCR_WORD` – word to detect (default: `Metinul`)
- `MIN_WORD_CONFIDENCE` – OCR confidence threshold
- `OCR_PSM` – Tesseract page segmentation mode

## Run
Install dependencies, then run the script.

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Notes
- OCR requires Tesseract to be installed on your system.
- If Tesseract isn't in PATH, set `TESSERACT_CMD` environment variable to the full path.
