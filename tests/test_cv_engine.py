"""CV 模块独立测试 — 不依赖 Flask，直接测 cv_engine.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cv_engine import CVEngine, load_rules, save_report

BASE = Path(__file__).resolve().parent.parent
RULES_PATH = BASE / "default_rules.json"
MODEL_PATH = BASE / "models" / "yolo11n.pt"
TEST_OUTPUT = BASE / "outputs" / "test_cv_engine"


def test_model_load():
    """测试 1: 模型加载"""
    print("=" * 50)
    print("TEST 1: 模型加载")
    cv = CVEngine(model_path=MODEL_PATH)
    assert cv.is_ready(), f"模型加载失败: {cv.load_error}"
    print(f"  PASS — 模型就绪: {cv.model_name}")
    return cv


def test_rules_load():
    """测试 2: 规则配置加载"""
    print("=" * 50)
    print("TEST 2: 规则配置加载")
    rules = load_rules(RULES_PATH)
    assert "risk_classes" in rules, "缺少 risk_classes"
    assert "review_confidence" in rules, "缺少 review_confidence"
    print(f"  PASS — 风险类别: {rules['risk_classes']}")
    print(f"  PASS — 提醒类别: {rules['warning_classes']}")
    print(f"  PASS — 阈值: reject={rules['reject_confidence']}, review={rules['review_confidence']}")
    return rules


def test_image_detect(cv: CVEngine, image_path: Path):
    """测试 3: 图片检测"""
    print("=" * 50)
    print(f"TEST 3: 图片检测 — {image_path.name}")
    detections = cv.detect_image(image_path)
    print(f"  PASS — 检测到 {len(detections)} 个目标")
    for d in detections:
        print(f"    {d['class_name']:15s}  conf={d['confidence']:.2f}  bbox={d['bbox']}")
    return detections


def test_video_detect(cv: CVEngine, video_path: Path):
    """测试 4: 视频采样检测"""
    print("=" * 50)
    print(f"TEST 4: 视频采样检测 — {video_path.name}")
    frames = cv.detect_video_frames(video_path, interval_sec=1.0, max_frames=30)
    total_dets = sum(len(f["detections"]) for f in frames)
    print(f"  PASS — 采样 {len(frames)} 帧, 共 {total_dets} 个检测结果")
    for f in frames[:5]:  # 只显示前 5 帧
        print(f"    帧 {f['frame_index']:5d}  {f['time_sec']:6.2f}s  {len(f['detections'])} 个目标")
    if len(frames) > 5:
        print(f"    ... 还有 {len(frames) - 5} 帧")
    return frames


def test_evaluate_rules(cv: CVEngine, detections: list[dict], rules: dict, label: str):
    """测试 5: 规则评估"""
    print("=" * 50)
    print(f"TEST 5: 规则评估 — {label}")
    result = cv.evaluate_rules(detections, rules)
    print(f"  PASS — 结论: {result['conclusion']} ({result['conclusion_text']})")
    print(f"  PASS — 原因: {result['reason']}")
    print(f"  PASS — 触发项: {len(result['risk_triggers'])} 条")
    print(f"  PASS — 证据帧: {result['evidence_frames']}")
    print(f"  PASS — 摘要: {result['summary']}")
    return result


def test_analyze_asset(cv: CVEngine, asset_path: Path, rules: dict, label: str):
    """测试 6: 完整分析流程"""
    print("=" * 50)
    print(f"TEST 6: 完整分析 — {label}")
    job_dir = TEST_OUTPUT / label
    report = cv.analyze_asset(asset_path, job_dir, rules)

    print(f"  PASS — 素材: {report['asset_name']}")
    print(f"  PASS — 类型: {report['media_type']}")
    print(f"  PASS — 机器结论: {report['review']['machine_conclusion']} ({report['review']['machine_conclusion_text']})")
    print(f"  PASS — 采样帧数: {report['summary']['sampled_frames']}")
    print(f"  PASS — 检测总数: {report['summary']['total_detections']}")
    print(f"  PASS — 最高置信度: {report['summary']['max_confidence']}")
    print(f"  PASS — 证据帧: {len(report['evidence_frames'])} 张")

    # 保存报告
    save_report(report, job_dir / "analysis_report.json")
    print(f"  PASS — 报告已保存: {job_dir / 'analysis_report.json'}")

    # 检查证据帧文件
    kf_dir = job_dir / "evidence"
    if kf_dir.exists():
        kf_files = list(kf_dir.glob("*.jpg"))
        print(f"  PASS — 证据帧文件: {len(kf_files)} 个")
        for kf in kf_files:
            print(f"    {kf.name} ({kf.stat().st_size} bytes)")

    return report


# ==================== 主入口 ====================

def main():
    print("\n" + "=" * 50)
    print("  Day08 CV 模块独立测试")
    print("=" * 50)

    # ---- 准备 ----
    TEST_OUTPUT.mkdir(parents=True, exist_ok=True)

    # 找测试素材：优先使用人工筛过的清晰样本，避免候选目录里的误检/无命中图片影响测试覆盖。
    preferred_images = [
        BASE / "assets" / "review_reject_knife_clear.jpg",
        BASE / "assets" / "review_reject_scissors.jpg",
        BASE / "assets" / "review_warning_wine_bottle_clear.jpg",
        BASE / "assets" / "review_person_only.jpg",
    ]
    test_images = [p for p in preferred_images if p.exists()]
    if not test_images:
        test_images = sorted((BASE / "assets").glob("review_*.jpg"))
    test_videos = sorted((BASE / "assets").rglob("*"))
    test_videos = [p for p in test_videos if p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}]

    # ---- 测试 1+2: 基础组件 ----
    cv = test_model_load()
    rules = test_rules_load()

    # ---- 测试 3+5+6: 图片 ----
    if test_images:
        img_path = test_images[0]
        dets = test_image_detect(cv, img_path)
        test_evaluate_rules(cv, [{"frame_index": 0, "time_sec": 0.0, "detections": dets, "evidence_image": ""}], rules, img_path.name)
        test_analyze_asset(cv, img_path, rules, "image_test")
    else:
        print("\n[SKIP] assets/ 下没有测试图片，请放入图片后重试")

    # ---- 测试 4+5+6: 视频 ----
    if test_videos:
        vid_path = test_videos[0]
        frames = test_video_detect(cv, vid_path)
        test_evaluate_rules(cv, frames, rules, vid_path.name)
        test_analyze_asset(cv, vid_path, rules, "video_test")
    else:
        print("\n[SKIP] assets/ 下没有测试视频，请放入视频后重试")

    # ---- 测试 7: 边界情况 ----
    print("=" * 50)
    print("TEST 7: 边界情况 — 空检测结果")
    result = cv.evaluate_rules([], rules)
    assert result["conclusion"] == "pass", f"空检测应返回 pass，实际: {result['conclusion']}"
    print(f"  PASS — 空检测 → {result['conclusion']} ({result['conclusion_text']})")

    # 不存在文件
    print("=" * 50)
    print("TEST 8: 异常 — 不存在的文件")
    try:
        cv.detect_image(Path("__nonexistent__.jpg"))
        print("  FAIL — 应该抛出异常")
    except FileNotFoundError as e:
        print(f"  PASS — 正确抛出 FileNotFoundError: {e}")

    print("\n" + "=" * 50)
    print("  测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
