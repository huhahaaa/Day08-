"""CV 审核引擎：YOLO 推理 + 规则判断 + 证据帧采集"""
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO


class CVEngine:
    """封装 YOLO 模型加载、推理、审核规则评估"""

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.model_name = self.model_path.name
        self._model = None
        self._load_model()

    def _load_model(self):
        """加载 YOLO 模型"""
        try:
            if self.model_path.exists():
                self._model = YOLO(str(self.model_path))
            else:
                # 自动下载
                self._model = YOLO("yolo11n.pt")
                # 保存到指定路径
                self._model.export(format="torchscript")
                if not self.model_path.parent.exists():
                    self.model_path.parent.mkdir(parents=True)
        except Exception as e:
            print(f"[CVEngine] 模型加载失败: {e}")
            self._model = None

    def is_ready(self) -> bool:
        """模型是否加载成功"""
        return self._model is not None

    def detect_image(self, image_path: Path) -> list[dict]:
        """对单张图片进行 YOLO 推理，返回检测结果列表"""
        if not self.is_ready():
            return []

        img = cv2.imread(str(image_path))
        if img is None:
            return []

        results = self._model(img, verbose=False)
        detections = self._parse_results(results, img)
        return detections

    def detect_frame(self, frame: np.ndarray) -> list[dict]:
        """对单帧（numpy 数组）进行检测，返回检测结果列表"""
        if not self.is_ready():
            return []
        results = self._model(frame, verbose=False)
        return self._parse_results(results, frame)

    def _parse_results(self, results, img) -> list[dict]:
        """解析 YOLO 结果"""
        detections = []
        if results and results[0].boxes:
            boxes = results[0].boxes
            h, w = img.shape[:2]
            for box in boxes:
                cls_id = int(box.cls[0])
                cls_name = results[0].names[cls_id]
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()
                # 归一化坐标（可选），这里直接返回像素坐标
                detections.append({
                    "class_name": cls_name,
                    "confidence": round(conf, 4),
                    "bbox": [round(x, 2) for x in xyxy]
                })
        return detections

    def detect_video_frames(self, video_path: Path, interval_sec: float = 1.0, max_frames: int = 30) -> list[dict]:
        """对视频按时间间隔采样帧，逐帧 YOLO 推理"""
        if not self.is_ready():
            return []

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        frame_results = []
        sample_step = max(1, int(fps * interval_sec))
        frame_count = 0
        analyzed = 0

        while frame_count < total_frames and analyzed < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
            ret, frame = cap.read()
            if not ret:
                break

            detections = self.detect_frame(frame)

            frame_results.append({
                "frame": frame_count,
                "time_sec": round(frame_count / fps, 2),
                "detections": detections,
                "count": len(detections)
            })

            frame_count += sample_step
            analyzed += 1

        cap.release()
        return frame_results

    def evaluate_rules(self, detections: list[dict], rules: dict) -> dict:
        """根据审核规则评估检测结果"""
        risk_classes = rules.get("risk_classes", ["person", "car"])
        reject_threshold = rules.get("reject_confidence", 0.60)
        review_threshold = rules.get("review_confidence", 0.35)
        min_evidence = rules.get("min_evidence_frames", 1)

        # 统计
        all_detections = []
        risk_triggers = []
        max_conf = 0.0

        for item in detections:
            # 如果是视频帧结果，需要展开 detections
            if "detections" in item:
                for d in item["detections"]:
                    all_detections.append(d)
            else:
                all_detections.append(item)

        for d in all_detections:
            conf = d.get("confidence", 0)
            cls = d.get("class_name", "")
            if conf > max_conf:
                max_conf = conf
            if cls in risk_classes and conf >= reject_threshold:
                risk_triggers.append({"class": cls, "confidence": conf})

        # 判断结论
        if risk_triggers:
            conclusion = "reject"
            reason = f"检测到高风险类别: {', '.join(set([t['class'] for t in risk_triggers]))}"
        elif max_conf >= review_threshold:
            conclusion = "review"
            reason = f"检测到目标，最大置信度 {max_conf:.2f} 处于待复核区间"
        elif len(all_detections) > 0:
            conclusion = "review"
            reason = f"检测到 {len(all_detections)} 个目标，置信度较低"
        else:
            conclusion = "pass"
            reason = "未检测到目标或规则目标"

        return {
            "verdict": conclusion,
            "reason": reason,
            "risk_triggers": risk_triggers,
            "total_detections": len(all_detections),
            "max_confidence": round(max_conf, 4),
            "settings": rules
        }

    def draw_boxes(self, image_path: Path, detections: list[dict], output_path: Path) -> Path:
        """在图片上绘制检测框并保存"""
        img = cv2.imread(str(image_path))
        if img is None:
            return output_path

        img = self._draw_boxes_on_image(img, detections)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), img)
        return output_path

    def draw_boxes_on_frame(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """在帧上绘制检测框，返回绘制后的帧"""
        return self._draw_boxes_on_image(frame, detections)

    def _draw_boxes_on_image(self, img: np.ndarray, detections: list[dict]) -> np.ndarray:
        """内部绘制函数"""
        for d in detections:
            bbox = d.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = [int(x) for x in bbox[:4]]
            cls = d.get("class_name", "unknown")
            conf = d.get("confidence", 0)

            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{cls} {conf:.2f}"
            cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return img