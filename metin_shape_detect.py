import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import cv2
import numpy as np


@dataclass
class DetectConfig:
    blur_ksize: int = 5
    canny1: int = 60
    canny2: int = 160
    min_area: int = 1500
    max_area: int = 120000
    min_ar: float = 0.4
    max_ar: float = 3.5
    min_solidity: float = 0.2
    min_extent: float = 0.18
    per_area_min: float = 0.05
    per_area_max: float = 0.25
    template_area_ratio_min: float = 0.4
    template_area_ratio_max: float = 3.2
    match_thresh: float = 0.22
    morph_kernel: int = 5
    dilate_iter: int = 1
    close_iter: int = 2
    nms_iou: float = 0.3


def preprocess_edges(img: np.ndarray, cfg: DetectConfig) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (cfg.blur_ksize, cfg.blur_ksize), 0)
    edges = cv2.Canny(blur, cfg.canny1, cfg.canny2)

    if cfg.morph_kernel > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (cfg.morph_kernel, cfg.morph_kernel)
        )
        edges = cv2.dilate(edges, kernel, iterations=cfg.dilate_iter)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=cfg.close_iter)

    return edges


def largest_contour(contours: List[np.ndarray]) -> np.ndarray:
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def contour_metrics(cnt: np.ndarray) -> Dict[str, float]:
    x, y, w, h = cv2.boundingRect(cnt)
    area = cv2.contourArea(cnt)
    hull = cv2.convexHull(cnt)
    hull_area = max(cv2.contourArea(hull), 1.0)
    aspect_ratio = h / max(float(w), 1.0)
    solidity = area / hull_area
    extent = area / max(float(w * h), 1.0)
    return {
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "area": area,
        "aspect_ratio": aspect_ratio,
        "solidity": solidity,
        "extent": extent,
    }


def detect_metins(
    frame: np.ndarray,
    template: np.ndarray,
    cfg: DetectConfig = None,
    exclude_rects: Optional[List[Tuple[int, int, int, int]]] = None,
) -> List[Dict[str, object]]:
    if cfg is None:
        cfg = DetectConfig()

    template_edges = preprocess_edges(template, cfg)
    t_contours, _ = cv2.findContours(
        template_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    t_cnt = largest_contour(t_contours)
    if t_cnt is None:
        return []
    t_metrics = contour_metrics(t_cnt)
    t_area = max(t_metrics["area"], 1.0)
    t_hull = cv2.convexHull(t_cnt)

    edges = preprocess_edges(frame, cfg)
    edges = apply_exclude_mask(edges, exclude_rects)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    results: List[Dict[str, object]] = []
    for cnt in contours:
        metrics = contour_metrics(cnt)
        area = metrics["area"]
        if area < cfg.min_area or area > cfg.max_area:
            continue

        ar = metrics["aspect_ratio"]
        if ar < cfg.min_ar or ar > cfg.max_ar:
            continue

        if metrics["solidity"] < cfg.min_solidity:
            continue

        if metrics["extent"] < cfg.min_extent:
            continue

        per = cv2.arcLength(cnt, True)
        per_area = per / max(area, 1.0)
        if per_area < cfg.per_area_min or per_area > cfg.per_area_max:
            continue

        area_ratio = area / t_area
        if (
            area_ratio < cfg.template_area_ratio_min
            or area_ratio > cfg.template_area_ratio_max
        ):
            continue

        score = cv2.matchShapes(cv2.convexHull(cnt), t_hull, cv2.CONTOURS_MATCH_I1, 0.0)
        if score > cfg.match_thresh:
            continue

        cx, cy = contour_center(cnt, metrics)
        results.append(
            {
                "x": metrics["x"],
                "y": metrics["y"],
                "w": metrics["w"],
                "h": metrics["h"],
                "center": (cx, cy),
                "score": float(score),
            }
        )

    return results


def contour_center(cnt: np.ndarray, metrics: Dict[str, float]) -> Tuple[int, int]:
    m = cv2.moments(cnt)
    if m["m00"] != 0:
        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        return cx, cy
    return int(metrics["x"] + metrics["w"] / 2), int(metrics["y"] + metrics["h"] / 2)


def detect_metins_multi(
    frame: np.ndarray,
    templates: List[np.ndarray],
    cfg: DetectConfig = None,
    exclude_rects: Optional[List[Tuple[int, int, int, int]]] = None,
) -> List[Dict[str, object]]:
    if cfg is None:
        cfg = DetectConfig()

    all_results: List[Dict[str, object]] = []
    for template in templates:
        if template is None:
            continue
        all_results.extend(detect_metins(frame, template, cfg, exclude_rects))

    return non_max_suppression(all_results, cfg.nms_iou)


def non_max_suppression(
    detections: List[Dict[str, object]], iou_thresh: float
) -> List[Dict[str, object]]:
    if not detections:
        return []

    # Lower match score is better.
    detections = sorted(detections, key=lambda d: d["score"])
    picked: List[Dict[str, object]] = []

    for det in detections:
        if all(iou(det, kept) < iou_thresh for kept in picked):
            picked.append(det)

    return picked


def iou(a: Dict[str, object], b: Dict[str, object]) -> float:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = ax1 + a["w"], ay1 + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = bx1 + b["w"], by1 + b["h"]

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = a["w"] * a["h"]
    area_b = b["w"] * b["h"]
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def draw_detections(frame: np.ndarray, detections: List[Dict[str, object]]) -> np.ndarray:
    out = frame.copy()
    for det in detections:
        x, y, w, h = det["x"], det["y"], det["w"], det["h"]
        cx, cy = det["center"]
        score = det["score"]
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.circle(out, (cx, cy), 3, (0, 255, 0), -1)
        cv2.putText(
            out,
            f"{score:.2f}",
            (x, max(0, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    return out


def run_tuner(frame: np.ndarray, template: np.ndarray, cfg: DetectConfig) -> None:
    cv2.namedWindow("tune", cv2.WINDOW_NORMAL)

    def noop(_val: int) -> None:
        return None

    cv2.createTrackbar("canny1", "tune", cfg.canny1, 255, noop)
    cv2.createTrackbar("canny2", "tune", cfg.canny2, 255, noop)
    cv2.createTrackbar("min_area", "tune", cfg.min_area, 200000, noop)
    cv2.createTrackbar("max_area", "tune", cfg.max_area, 300000, noop)
    cv2.createTrackbar("match_x100", "tune", int(cfg.match_thresh * 100), 100, noop)

    while True:
        cfg.canny1 = cv2.getTrackbarPos("canny1", "tune")
        cfg.canny2 = cv2.getTrackbarPos("canny2", "tune")
        cfg.min_area = cv2.getTrackbarPos("min_area", "tune")
        cfg.max_area = cv2.getTrackbarPos("max_area", "tune")
        cfg.match_thresh = cv2.getTrackbarPos("match_x100", "tune") / 100.0

        detections = detect_metins(frame, template, cfg)
        view = draw_detections(frame, detections)
        cv2.imshow("tune", view)
        key = cv2.waitKey(30) & 0xFF
        if key == 27 or key == ord("q"):
            break

    cv2.destroyAllWindows()


def load_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Failed to read image: {path}")
    return img


def apply_exclude_mask(
    edges: np.ndarray,
    exclude_rects: Optional[List[Tuple[int, int, int, int]]],
) -> np.ndarray:
    if not exclude_rects:
        return edges

    mask = np.ones(edges.shape[:2], dtype=np.uint8) * 255
    for x1, y1, x2, y2 in exclude_rects:
        mask[y1:y2, x1:x2] = 0
    return cv2.bitwise_and(edges, edges, mask=mask)


def default_ui_exclude(frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
    h, w = frame.shape[:2]
    return [
        (0, 0, int(0.28 * w), int(0.22 * h)),
        (int(0.78 * w), 0, w, int(0.26 * h)),
        (0, int(0.82 * h), w, h),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab", default="image_lab", help="Folder with inputs")
    parser.add_argument("--tune", action="store_true", help="Enable trackbar tuner")
    parser.add_argument(
        "--no-ui-mask", action="store_true", help="Disable UI exclusion mask"
    )
    args = parser.parse_args()

    lab = Path(__file__).resolve().parent / args.lab
    frame_paths = [lab / "ss1.png", lab / "ss2.png"]
    template_paths = [lab / "shape1.png", lab / "shape2.png", lab / "shape3.png"]

    templates = [load_image(p) for p in template_paths]
    cfg = DetectConfig()

    if args.tune:
        run_tuner(load_image(frame_paths[0]), templates[0], cfg)
        return

    for frame_path in frame_paths:
        frame = load_image(frame_path)
        exclude_rects = None if args.no_ui_mask else default_ui_exclude(frame)
        detections = detect_metins_multi(frame, templates, cfg, exclude_rects)
        out = draw_detections(frame, detections)
        out_path = frame_path.with_name(f"{frame_path.stem}_detected.png")
        cv2.imwrite(str(out_path), out)

        print(f"{frame_path.name}: {len(detections)} detections -> {out_path.name}")
        for det in detections:
            print(
                "  "
                + str(
                    {
                        "x": det["x"],
                        "y": det["y"],
                        "w": det["w"],
                        "h": det["h"],
                        "center": det["center"],
                        "score": round(det["score"], 3),
                    }
                )
            )


if __name__ == "__main__":
    main()
