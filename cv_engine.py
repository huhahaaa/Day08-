"""CV 审核引擎 — YOLO 推理 + 规则判断 + 证据帧采集"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO

# 控制台输出编码修正
sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None


class CVEngine:
    """封装 YOLO 模型加载、推理、审核规则评估、证据帧保存"""

    # ---- 颜色常量 ----
    COLOR_RISK = (0, 0, 255)       # 红 - 高风险
    COLOR_WARNING = (0, 215, 255)  # 黄 - 提醒
    COLOR_NORMAL = (0, 255, 0)     # 绿 - 其他
    SECONDARY_ALLOWED_CLASSES = {"gun", "weapon", "rifle"}

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self._model: Optional[YOLO] = None
        self._models: list[tuple[str, YOLO]] = []
        self.model_names: list[str] = []
        self.extra_model_errors: list[str] = []
        self.load_error: Optional[str] = None
        self.secondary_model_path = self.model_path.with_name("custom_gun.pt")
        self.model_name = self.model_path.name

        if not self.model_path.exists():
            self.load_error = f"模型文件不存在: {self.model_path}"
            return

        try:
            self._model = YOLO(str(self.model_path))
            self._models.append((self.model_path.name, self._model))
            self.model_names.append(self.model_path.name)
        except Exception as exc:
            self.load_error = f"模型加载失败: {exc}"
            return

        if self.secondary_model_path.exists():
            try:
                extra_model = YOLO(str(self.secondary_model_path))
                self._models.append((self.secondary_model_path.name, extra_model))
                self.model_names.append(self.secondary_model_path.name)
            except Exception as exc:
                self.extra_model_errors.append(
                    f"{self.secondary_model_path.name} 加载失败: {exc}"
                )

        self.model_name = " + ".join(self.model_names) if self.model_names else self.model_path.name

    # ==================== 公共 API ====================

    def is_ready(self) -> bool:
        """模型是否加载成功"""
        return self._model is not None

    def detect_image(self, image_path: Path) -> list[dict]:
        """对单张图片 YOLO 推理，返回结构化检测结果

        Raises:
            FileNotFoundError: 图片文件不存在
            ValueError: 图片读取失败或损坏
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {image_path}")

        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"图片读取失败或文件损坏: {image_path}")

        return self._run_yolo(img)

    def detect_video_frames(
        self,
        video_path: Path,
        interval_sec: float = 1.0,
        max_frames: int = 120,
    ) -> list[dict]:
        """对视频按时间间隔采样帧，逐帧 YOLO 推理

        Returns:
            [{frame_index, time_sec, detections: [...]}, ...]

        Raises:
            FileNotFoundError: 视频文件不存在
            ValueError: 视频读取失败、FPS 无效、无可分析帧
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"视频读取失败或格式不支持: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            cap.release()
            raise ValueError("视频 FPS 无效")

        interval_frames = max(1, int(fps * interval_sec))
        results: list[dict] = []
        frame_idx = 0
        sampled = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % interval_frames == 0:
                if sampled >= max_frames:
                    break

                time_sec = round(frame_idx / fps, 2)
                detections = self._run_yolo(frame)
                results.append({
                    "frame_index": frame_idx,
                    "time_sec": time_sec,
                    "detections": detections,
                })
                sampled += 1

            frame_idx += 1

        cap.release()

        if not results:
            raise RuntimeError("视频没有可分析帧")

        return results

    def evaluate_rules(self, detections: list[dict], rules: dict) -> dict:
        """根据审核规则评估检测结果，返回 pass / review / reject

        支持两种输入格式：
        - 图片：[{class_name, confidence, bbox, ...}, ...]
        - 视频：[{frame_index, time_sec, detections: [...]}, ...]

        内部统一展平后再判断。
        """
        risk_classes = set(rules.get("risk_classes", []))
        warning_classes = set(rules.get("warning_classes", []))
        reject_conf = float(rules.get("reject_confidence", 0.60))
        review_conf = float(rules.get("review_confidence", 0.35))

        flat_items = self._flatten_detections(detections)

        triggers: list[dict] = []
        for item in flat_items:
            class_name = item.get("class_name", "")
            confidence = float(item.get("confidence", 0))

            if class_name in risk_classes and confidence >= reject_conf:
                triggers.append({**item, "level": "reject"})
            elif class_name in risk_classes and confidence >= review_conf:
                triggers.append({**item, "level": "review"})
            elif class_name in warning_classes and confidence >= review_conf:
                triggers.append({**item, "level": "review"})

        # 结论优先级: reject > review > pass
        if any(t["level"] == "reject" for t in triggers):
            conclusion = "reject"
        elif any(t["level"] == "review" for t in triggers):
            conclusion = "review"
        else:
            conclusion = "pass"

        # 证据帧排序: reject 优先 > 置信度降序 > 时间升序
        triggers.sort(key=lambda t: (
            0 if t["level"] == "reject" else 1,
            -float(t.get("confidence", 0)),
            float(t.get("time_sec") or 0),
        ))

        evidence_frames: list[str] = []
        seen: set[str] = set()
        for t in triggers:
            img = t.get("evidence_image", "")
            if img and img not in seen:
                evidence_frames.append(img)
                seen.add(img)

        max_ev = int(rules.get("max_evidence_frames", 10))
        evidence_frames = evidence_frames[:max_ev]

        all_confs = [float(x.get("confidence", 0)) for x in flat_items]

        return {
            "conclusion": conclusion,
            "conclusion_text": self._conclusion_label(conclusion),
            "reason": self._build_reason(conclusion, triggers, rules),
            "risk_triggers": triggers,
            "evidence_frames": evidence_frames,
            "summary": {
                "total_detections": len(flat_items),
                "risk_hits": sum(1 for x in flat_items if x.get("class_name") in risk_classes),
                "warning_hits": sum(1 for x in flat_items if x.get("class_name") in warning_classes),
                "max_confidence": round(max(all_confs) if all_confs else 0, 4),
            },
        }

    def analyze_asset(self, asset_path: Path, job_dir: Path, rules: dict) -> dict:
        """统一入口：自动判断图片/视频 → 检测 → 绘制证据 → 规则评估 → 完整报告

        这是后端调用的主方法。返回完整的 analysis_report 字典，
        后端负责将结果写入 analysis_report.json。
        """
        asset_path = Path(asset_path)
        job_dir = Path(job_dir)
        evidence_dir = job_dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        sampled_frames_dir = job_dir / "sampled_frames"

        suffix = asset_path.suffix.lower()
        image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        video_exts = {".mp4", ".avi", ".mov", ".mkv"}

        if suffix in image_exts:
            media_type = "image"
            interval = None
            framed = self._analyze_image(asset_path, evidence_dir, rules)
        elif suffix in video_exts:
            media_type = "video"
            interval = float(rules.get("video_sample_interval_sec", 0.5))
            max_frames = int(rules.get("max_sample_frames", 120))
            sampled_frames_dir.mkdir(parents=True, exist_ok=True)
            framed = self._analyze_video(
                asset_path,
                evidence_dir,
                sampled_frames_dir,
                rules,
                interval,
                max_frames,
            )
        else:
            raise ValueError(f"格式不支持: {suffix}")

        rule_result = self.evaluate_rules(framed, rules)

        return {
            "job_id": "",  # 后端填充
            "asset_name": asset_path.name,
            "media_type": media_type,
            "model_name": self.model_name,
            "rules": {
                "risk_classes": rules.get("risk_classes", []),
                "warning_classes": rules.get("warning_classes", []),
                "reject_confidence": float(rules.get("reject_confidence", 0.60)),
                "review_confidence": float(rules.get("review_confidence", 0.35)),
                "video_sample_interval_sec": interval,
            },
            "review": {
                "machine_conclusion": rule_result["conclusion"],
                "machine_conclusion_text": rule_result["conclusion_text"],
                "reason": rule_result["reason"],
                "manual_conclusion": None,
                "reviewer": "",
                "note": "",
            },
            "summary": {
                "sampled_frames": len(framed),
                **rule_result["summary"],
            },
            "frames": framed,
            "evidence_frames": rule_result["evidence_frames"],
            "created_at": datetime.now().isoformat(),
        }

    def draw_evidence(
        self,
        image: np.ndarray,
        detections: list[dict],
        output_path: Path,
        rules: Optional[dict] = None,
    ) -> str:
        """在图像上绘制检测框并保存为证据图

        Args:
            image: BGR 图像
            detections: 检测结果列表
            output_path: 保存路径
            rules: 规则配置（决定框颜色）

        Returns:
            保存的绝对路径字符串
        """
        risk_classes = set((rules or {}).get("risk_classes", []))
        warning_classes = set((rules or {}).get("warning_classes", []))

        for det in detections:
            cls = det.get("class_name", "")
            conf = float(det.get("confidence", 0))
            bbox = det.get("bbox", [0, 0, 0, 0])
            x1, y1, x2, y2 = [int(v) for v in bbox]

            if cls in risk_classes:
                color = self.COLOR_RISK
            elif cls in warning_classes:
                color = self.COLOR_WARNING
            else:
                color = self.COLOR_NORMAL

            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            label = f"{cls} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            # 标签背景
            cv2.rectangle(image, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                image, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

        cv2.imwrite(str(output_path), image)
        return str(output_path)

    def draw_boxes(
        self,
        image_path: Path,
        detections: list[dict],
        output_path: Path,
        rules: Optional[dict] = None,
    ) -> str:
        """兼容旧后端调用：读取图片后绘制检测框。"""
        image_path = Path(image_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"图片读取失败或文件损坏: {image_path}")

        return self.draw_evidence(img, detections, output_path, rules)

    # ==================== 内部方法 ====================

    def _analyze_image(self, image_path: Path, evidence_dir: Path, rules: dict) -> list[dict]:
        """图片审核：读取 → 检测 → 保存证据"""
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"图片读取失败或文件损坏: {image_path}")

        detections = self._run_yolo(img)

        evidence_rel = ""
        if self._should_save_evidence(detections, rules):
            evidence_rel = "evidence/image_evidence.jpg"
            self.draw_evidence(img.copy(), detections, evidence_dir / "image_evidence.jpg", rules)

        return [{
            "frame_index": 0,
            "time_sec": 0.0,
            "detections": detections,
            "evidence_image": evidence_rel,
        }]

    def _analyze_video(
        self,
        video_path: Path,
        evidence_dir: Path,
        sampled_frames_dir: Path,
        rules: dict,
        interval_sec: float,
        max_frames: int,
    ) -> list[dict]:
        """视频审核：打开 → 保存采样帧 → 逐采样帧检测 → 选择性保存证据"""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"视频读取失败或格式不支持: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            cap.release()
            raise ValueError("视频 FPS 无效")

        interval_frames = max(1, int(fps * interval_sec))
        framed: list[dict] = []
        frame_idx = 0
        sampled = 0
        evidence_count = 0
        max_evidence = int(rules.get("max_evidence_frames", 10))

        risk_classes = set(rules.get("risk_classes", []))
        warning_classes = set(rules.get("warning_classes", []))
        review_conf = float(rules.get("review_confidence", 0.35))

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % interval_frames == 0:
                if sampled >= max_frames:
                    break

                time_sec = round(frame_idx / fps, 2)
                detections = self._run_yolo(frame)
                sampled_rel = f"sampled_frames/frame_{frame_idx:06d}.jpg"
                cv2.imwrite(str(sampled_frames_dir / f"frame_{frame_idx:06d}.jpg"), frame)

                evidence_rel = ""
                if evidence_count < max_evidence:
                    for d in detections:
                        cls = d.get("class_name", "")
                        conf = float(d.get("confidence", 0))
                        if cls in risk_classes and conf >= review_conf:
                            evidence_rel = f"evidence/frame_{frame_idx:06d}.jpg"
                            self.draw_evidence(
                                frame.copy(), detections,
                                evidence_dir / f"frame_{frame_idx:06d}.jpg", rules,
                            )
                            evidence_count += 1
                            break
                        elif cls in warning_classes and conf >= review_conf:
                            evidence_rel = f"evidence/frame_{frame_idx:06d}.jpg"
                            self.draw_evidence(
                                frame.copy(), detections,
                                evidence_dir / f"frame_{frame_idx:06d}.jpg", rules,
                            )
                            evidence_count += 1
                            break

                framed.append({
                    "frame_index": frame_idx,
                    "time_sec": time_sec,
                    "sampled_image": sampled_rel,
                    "detections": detections,
                    "evidence_image": evidence_rel,
                })
                sampled += 1

            frame_idx += 1

        cap.release()

        if not framed:
            raise RuntimeError("视频没有可分析帧")

        # 确保证据帧不低于 min_evidence_frames（用最高置信度检测帧补齐）
        min_ev = int(rules.get("min_evidence_frames", 1))
        if evidence_count < min_ev and framed:
            # 从未保存证据的帧中按最高置信度排序补录
            candidates = []
            for f in framed:
                if f["evidence_image"]:
                    continue
                best_conf = max(
                    (float(d.get("confidence", 0)) for d in f["detections"]),
                    default=0,
                )
                if best_conf > 0:
                    candidates.append((best_conf, f))
            candidates.sort(key=lambda x: x[0], reverse=True)

            cap2 = cv2.VideoCapture(str(video_path))
            for _, f_item in candidates:
                if evidence_count >= min_ev:
                    break
                fi = f_item["frame_index"]
                cap2.set(cv2.CAP_PROP_POS_FRAMES, fi)
                ok, frame = cap2.read()
                if not ok:
                    continue
                f_item["evidence_image"] = f"evidence/frame_{fi:06d}.jpg"
                self.draw_evidence(
                    frame, f_item["detections"],
                    evidence_dir / f"frame_{fi:06d}.jpg", rules,
                )
                evidence_count += 1
            cap2.release()

        return framed

    def _run_yolo(self, image: np.ndarray) -> list[dict]:
        """单次 YOLO 推理"""
        if not self._models:
            raise RuntimeError(self.load_error or "模型未加载")

        detections: list[dict] = []

        for model_name, model in self._models:
            results = model(image, verbose=False)
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for i in range(len(boxes)):
                    class_id = int(boxes.cls[i].item())
                    class_name = model.names.get(class_id, "unknown")
                    if model_name == self.secondary_model_path.name:
                        if class_name.lower() not in self.SECONDARY_ALLOWED_CLASSES:
                            continue
                    detections.append({
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": round(float(boxes.conf[i].item()), 4),
                        "bbox": [int(round(v)) for v in boxes.xyxy[i].tolist()],
                        "source_model": model_name,
                    })

        return detections

    def _flatten_detections(self, detections: list[dict]) -> list[dict]:
        """展平检测结果：视频帧结构 → 统一扁平列表"""
        flat: list[dict] = []
        for item in detections:
            if "detections" in item:
                for det in item["detections"]:
                    flat.append({
                        **det,
                        "frame_index": item.get("frame_index"),
                        "time_sec": item.get("time_sec"),
                        "evidence_image": item.get("evidence_image"),
                    })
            else:
                flat.append(item)
        return flat

    def _should_save_evidence(self, detections: list[dict], rules: dict) -> bool:
        """判断是否需要保存证据帧"""
        risk_classes = set(rules.get("risk_classes", []))
        warning_classes = set(rules.get("warning_classes", []))
        review_conf = float(rules.get("review_confidence", 0.35))
        for d in detections:
            cls = d.get("class_name", "")
            conf = float(d.get("confidence", 0))
            if cls in risk_classes and conf >= review_conf:
                return True
            if cls in warning_classes and conf >= review_conf:
                return True
        return False

    # ---- 静态工具方法 ----

    @staticmethod
    def _conclusion_label(conclusion: str) -> str:
        return {"pass": "通过", "review": "待复核", "reject": "不通过"}.get(conclusion, conclusion)

    @staticmethod
    def _build_reason(conclusion: str, triggers: list[dict], rules: dict) -> str:
        if conclusion == "pass":
            return "未发现达到审核阈值的风险目标"

        reject_triggers = [t for t in triggers if t["level"] == "reject"]
        if reject_triggers:
            top = reject_triggers[0]
            return (
                f"检测到高风险类别 {top.get('class_name')}，"
                f"最高置信度 {top.get('confidence')}，"
                f"超过不通过阈值 {rules.get('reject_confidence', 0.60)}"
            )

        review_triggers = [t for t in triggers if t["level"] == "review"]
        if review_triggers:
            top = review_triggers[0]
            if top.get("class_name") in set(rules.get("risk_classes", [])):
                return (
                    f"检测到疑似高风险类别 {top.get('class_name')}，"
                    f"置信度 {top.get('confidence')}，需要人工复核"
                )
            return (
                f"检测到提醒类别 {top.get('class_name')}，"
                f"置信度 {top.get('confidence')}，建议人工确认"
            )

        return "未知审核结论"


# ==================== 便捷函数 ====================

def load_rules(rules_path: Path) -> dict:
    """从 JSON 文件加载审核规则"""
    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_report(report: dict, output_path: Path) -> None:
    """保存 analysis_report.json"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
