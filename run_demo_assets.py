"""Run selected demo assets and write outputs into one clean directory."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cv_engine import CVEngine, load_rules, save_report


BASE_DIR = Path(__file__).resolve().parent
ASSET_NAMES = [
    "review_reject_scissors.jpg",
    "review_reject_knife_clear.jpg",
    "review_reject_baseball_bat.jpg",
    "review_warning_wine_bottle_clear.jpg",
    "review_person_only.jpg",
]


def main() -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = BASE_DIR / "outputs" / f"demo_run_{run_id}"
    output_root.mkdir(parents=True, exist_ok=True)

    rules = load_rules(BASE_DIR / "default_rules.json")
    cv = CVEngine(BASE_DIR / "models" / "yolo11n.pt")
    if not cv.is_ready():
        raise RuntimeError(cv.load_error or "YOLO model is not ready")

    print(f"Output directory: {output_root}")
    print()

    for asset_name in ASSET_NAMES:
        asset_path = BASE_DIR / "assets" / asset_name
        if not asset_path.exists():
            print(f"SKIP {asset_name}: file not found")
            continue

        job_dir = output_root / asset_path.stem
        report = cv.analyze_asset(asset_path, job_dir, rules)
        report["job_id"] = asset_path.stem
        save_report(report, job_dir / "analysis_report.json")

        conclusion = report["review"]["machine_conclusion_text"]
        evidence_count = len(report.get("evidence_frames", []))
        print(f"{asset_name}: {conclusion}, evidence={evidence_count}")

    print()
    print(f"Done. Open this folder: {output_root}")


if __name__ == "__main__":
    main()
