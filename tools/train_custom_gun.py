from __future__ import annotations

import argparse
import json
import math
import shutil
import numbers
import warnings
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "gun_raw"
YOLO_DIR = BASE_DIR / "data" / "gun_yolo"
RUNS_DIR = BASE_DIR / "runs" / "gun"
SOURCE_REPO = "Subh775/WeaponDetection_Grouped"
CLASS_NAMES = ["gun", "knife", "person"]
SPLIT_FILES = {
    "train": "data/train-00000-of-00001.parquet",
    "validation": "data/validation-00000-of-00001.parquet",
    "test": "data/test-00000-of-00001.parquet",
}


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.name}")
        return

    print(f"[download] {dest.name}")
    try:
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return
    except requests.exceptions.SSLError:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")
        print("  -> SSL 校验失败，降级为 verify=False")
        with requests.get(url, stream=True, timeout=120, verify=False) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)


def local_candidates(split: str) -> list[Path]:
    return [
        RAW_DIR / f"data_{split}-00000-of-00001.parquet",
        RAW_DIR / f"{split}-00000-of-00001.parquet",
        RAW_DIR / f"{split}.parquet",
    ]


def value_to_python(value: Any) -> Any:
    if hasattr(value, "as_py"):
        return value.as_py()
    return value


def image_bytes_from_value(value: Any) -> bytes | None:
    value = value_to_python(value)
    if isinstance(value, dict):
        data = value.get("bytes")
        if data is None:
            return None
        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data)
        return bytes(data)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    return None


def category_to_id(value: Any) -> int | None:
    value = value_to_python(value)
    if isinstance(value, numbers.Integral):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        lookup = {
            "gun": 0,
            "GUN": 0,
            "knife": 1,
            "KNIFE": 1,
            "person": 2,
            "PERSON": 2,
        }
        return lookup.get(value)
    return None


def score_candidate(x1: float, y1: float, x2: float, y2: float, width: int, height: int):
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
        return None
    if x2 <= x1 or y2 <= y1:
        return None

    ix1 = max(0.0, min(x1, float(width)))
    iy1 = max(0.0, min(y1, float(height)))
    ix2 = max(0.0, min(x2, float(width)))
    iy2 = max(0.0, min(y2, float(height)))
    if ix2 <= ix1 or iy2 <= iy1:
        return None

    clipped_area = (ix2 - ix1) * (iy2 - iy1)
    full_area = max(1.0, float(width * height))
    area_ratio = clipped_area / full_area
    overflow = max(0.0, -x1) + max(0.0, -y1) + max(0.0, x2 - width) + max(0.0, y2 - height)

    score = clipped_area
    if 0.001 <= area_ratio <= 0.9:
        score += full_area * 0.1
    if x1 >= 0 and y1 >= 0 and x2 <= width and y2 <= height:
        score += full_area * 0.2
    if area_ratio > 0.95:
        score -= full_area * 0.25
    score -= overflow * max(width, height)
    return score, (ix1, iy1, ix2, iy2)


def infer_box(raw_box: list[float], width: int, height: int):
    if len(raw_box) != 4:
        return None

    a, b, c, d = [float(v) for v in raw_box]
    normalized = 0.0 <= min(a, b, c, d) and max(a, b, c, d) <= 1.5

    candidates: list[tuple[str, float, float, float, float]] = []
    if normalized:
        candidates.extend([
            ("xywh_norm", a * width, b * height, (a + c) * width, (b + d) * height),
            ("xyxy_norm", a * width, b * height, c * width, d * height),
            ("cxcywh_norm", (a - c / 2.0) * width, (b - d / 2.0) * height, (a + c / 2.0) * width, (b + d / 2.0) * height),
        ])

    candidates.extend([
        ("xywh_abs", a, b, a + c, b + d),
        ("xyxy_abs", a, b, c, d),
        ("cxcywh_abs", a - c / 2.0, b - d / 2.0, a + c / 2.0, b + d / 2.0),
    ])

    best_score = None
    best_box = None
    for _, x1, y1, x2, y2 in candidates:
        scored = score_candidate(x1, y1, x2, y2, width, height)
        if scored is None:
            continue
        score, box = scored
        if best_score is None or score > best_score:
            best_score = score
            best_box = box

    if best_box is None:
        return None

    x1, y1, x2, y2 = best_box
    xc = ((x1 + x2) / 2.0) / width
    yc = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return xc, yc, bw, bh


def ensure_source_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for split, rel_path in SPLIT_FILES.items():
        local_file = next((p for p in local_candidates(split) if p.exists() and p.stat().st_size > 0), None)
        if local_file is not None:
            print(f"[local] {local_file.name}")
            files[split] = local_file
            continue

        url = f"https://huggingface.co/datasets/{SOURCE_REPO}/resolve/main/{rel_path}"
        dest = RAW_DIR / f"data_{split}-00000-of-00001.parquet"
        download_file(url, dest)
        files[split] = dest
    return files


def write_data_yaml() -> Path:
    YOLO_DIR.mkdir(parents=True, exist_ok=True)
    data_yaml = YOLO_DIR / "data.yaml"
    content = (
        f"path: '{YOLO_DIR.as_posix()}'\n"
        "train: images/train\n"
        "val: images/validation\n"
        "test: images/test\n\n"
        f"nc: {len(CLASS_NAMES)}\n"
        "names:\n"
        f"  0: {CLASS_NAMES[0]}\n"
        f"  1: {CLASS_NAMES[1]}\n"
        f"  2: {CLASS_NAMES[2]}\n"
    )
    data_yaml.write_text(content, encoding="utf-8")
    return data_yaml


def convert_split(parquet_path: Path, split: str, limit: int = 0) -> dict[str, int]:
    import pyarrow.parquet as pq

    image_dir = YOLO_DIR / "images" / split
    label_dir = YOLO_DIR / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    pf = pq.ParquetFile(parquet_path)
    saved = 0
    skipped = 0
    class_counts = {name: 0 for name in CLASS_NAMES}

    for batch in pf.iter_batches(batch_size=32, columns=["image", "width", "height", "objects"]):
        for row in batch.to_pylist():
            if limit and saved >= limit:
                return {"images": saved, "skipped": skipped, **class_counts}

            image_bytes = image_bytes_from_value(row.get("image"))
            if not image_bytes:
                skipped += 1
                continue

            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if image is None:
                skipped += 1
                continue

            height = int(row.get("height") or image.shape[0])
            width = int(row.get("width") or image.shape[1])
            stem = f"{split}_{saved:06d}"
            image_path = image_dir / f"{stem}.jpg"
            label_path = label_dir / f"{stem}.txt"

            if not cv2.imwrite(str(image_path), image):
                skipped += 1
                continue

            objects = row.get("objects") or {}
            bboxes = objects.get("bbox") or []
            categories = objects.get("category") or []

            lines: list[str] = []
            for raw_box, category in zip(bboxes, categories):
                class_id = category_to_id(category)
                if class_id is None or class_id >= len(CLASS_NAMES):
                    continue
                box = infer_box(raw_box, width, height)
                if box is None:
                    continue
                xc, yc, bw, bh = box
                lines.append(f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
                class_counts[CLASS_NAMES[class_id]] += 1

            label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            saved += 1

    return {"images": saved, "skipped": skipped, **class_counts}


def prepare_dataset(limit: int = 0) -> Path:
    files = ensure_source_files()
    YOLO_DIR.mkdir(parents=True, exist_ok=True)

    summary = {}
    for split, parquet_path in files.items():
        print(f"[convert] {split}")
        summary[split] = convert_split(parquet_path, split, limit=limit)
        print(f"  images={summary[split]['images']} skipped={summary[split]['skipped']} gun={summary[split]['gun']} knife={summary[split]['knife']} person={summary[split]['person']}")

    data_yaml = write_data_yaml()
    meta = {
        "source_repo": SOURCE_REPO,
        "class_names": CLASS_NAMES,
        "splits": summary,
    }
    (YOLO_DIR / "dataset_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data_yaml


def train_model(data_yaml: Path, weights: Path, epochs: int, imgsz: int, batch: int, device: str) -> Path:
    model = YOLO(str(weights))
    model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=str(RUNS_DIR),
        name="custom_gun",
        exist_ok=True,
        patience=20,
        pretrained=True,
        verbose=True,
    )

    save_dir = Path(model.trainer.save_dir)
    best_path = save_dir / "weights" / "best.pt"
    if not best_path.exists():
        raise RuntimeError(f"训练完成但未找到 best.pt: {best_path}")

    output_model = BASE_DIR / "models" / "custom_gun.pt"
    output_model.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_path, output_model)
    return output_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and train the custom gun YOLO model.")
    parser.add_argument("--prepare-only", action="store_true", help="Only prepare the YOLO dataset, do not train.")
    parser.add_argument("--skip-prepare", action="store_true", help="Train with existing data/gun_yolo/data.yaml.")
    parser.add_argument("--limit-per-split", type=int, default=0, help="Limit converted images per split for smoke testing.")
    parser.add_argument("--weights", type=Path, default=BASE_DIR / "models" / "yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_yaml = YOLO_DIR / "data.yaml"
    if args.skip_prepare:
        if not data_yaml.exists():
            raise FileNotFoundError(f"未找到数据集配置，请先转换数据集: {data_yaml}")
        print(f"[skip] use existing dataset yaml: {data_yaml}")
    else:
        data_yaml = prepare_dataset(limit=args.limit_per_split)
        print(f"[ready] dataset yaml: {data_yaml}")

    if args.prepare_only:
        return

    output_model = train_model(
        data_yaml=data_yaml,
        weights=args.weights,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
    )
    print(f"[done] custom model saved to: {output_model}")


if __name__ == "__main__":
    main()
