import argparse
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import mss
import numpy as np

try:
    from detect_pm.telegram_notify import send_telegram_message
except ModuleNotFoundError:
    from telegram_notify import send_telegram_message

ROI_X = 1780
ROI_Y = 270
ROI_W = 110
ROI_H = 190

TEMPLATE_NAMES = ["template.png", "template_regular.png"]


def _load_template(template_path: Path) -> np.ndarray:
    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found or unreadable: {template_path}")
    return template


def _grab_screen_bgr() -> np.ndarray:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def detect_pm_flag(
    debug: bool = False,
    threshold: float = 0.9,
    screenshot_dir: Optional[Path] = None,
) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
    """
    Check the ROI for a PM envelope template (GM or regular player).
    Returns (flag, best_score, match_center) where match_center is the
    absolute screen (x, y) of the best match centre, or None if no match.
    """
    base_dir = Path(__file__).resolve().parent

    screen_bgr = _grab_screen_bgr()
    screen_h, screen_w = screen_bgr.shape[:2]

    if ROI_X + ROI_W > screen_w or ROI_Y + ROI_H > screen_h:
        raise ValueError("ROI is outside the captured screen bounds.")

    roi = screen_bgr[ROI_Y : ROI_Y + ROI_H, ROI_X : ROI_X + ROI_W]
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    best_flag = False
    best_score = 0.0
    best_center: Optional[Tuple[int, int]] = None
    best_tw, best_th = 0, 0
    best_loc = (0, 0)

    for tname in TEMPLATE_NAMES:
        tpath = base_dir / tname
        if not tpath.exists():
            continue
        tgray = _load_template(tpath)
        th, tw = tgray.shape[:2]
        if tw > ROI_W or th > ROI_H:
            continue

        result = cv2.matchTemplate(roi_gray, tgray, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val > best_score:
            best_score = max_val
            best_loc = max_loc
            best_tw, best_th = tw, th
            if max_val >= threshold:
                best_flag = True
                # Absolute screen position of the match centre
                best_center = (
                    ROI_X + max_loc[0] + tw // 2,
                    ROI_Y + max_loc[1] + th // 2,
                )

    if debug and best_flag:
        overlay = screen_bgr.copy()

        # ROI box
        cv2.rectangle(
            overlay,
            (ROI_X, ROI_Y),
            (ROI_X + ROI_W, ROI_Y + ROI_H),
            (0, 0, 255),
            2,
        )

        # Template match highlight
        top_left = (ROI_X + best_loc[0], ROI_Y + best_loc[1])
        bottom_right = (top_left[0] + best_tw, top_left[1] + best_th)
        cv2.rectangle(overlay, top_left, bottom_right, (0, 255, 0), 2)

        if screenshot_dir is None:
            screenshot_dir = base_dir
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        stamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = screenshot_dir / f"pm_debug_{stamp}.png"
        cv2.imwrite(str(out_path), overlay)

    return best_flag, float(best_score), best_center


def _print_status(flag: bool, score: float) -> None:
    stamp = time.strftime("%H:%M:%S")
    status = "PM detected" if flag else "PM not detected"
    print(f"[{stamp}] {status}. Score={score:.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="PM detector using template matching.")
    parser.add_argument("--debug", action="store_true", help="Save debug screenshot.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="Template match threshold (0-1).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between checks when running continuously.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single check and exit.",
    )
    args = parser.parse_args()
    notified = False

    if args.once:
        flag, score, _pos = detect_pm_flag(debug=args.debug, threshold=args.threshold)
        if flag:
            msg = f"PM detectat in joc. Score={score:.3f}."
            if not send_telegram_message(msg, debug=True):
                print("[PM] Nu am putut trimite mesaj Telegram (token/chat_id lipsa sau eroare).")
        _print_status(flag, score)
        return 0 if flag else 1

    print("Running continuous PM check. Press Ctrl+C to stop.")
    try:
        while True:
            flag, score, _pos = detect_pm_flag(debug=args.debug, threshold=args.threshold)
            if flag and not notified:
                msg = f"PM detectat in joc. Score={score:.3f}."
                if not send_telegram_message(msg, debug=True):
                    print("[PM] Nu am putut trimite mesaj Telegram (token/chat_id lipsa sau eroare).")
                notified = True
            _print_status(flag, score)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())