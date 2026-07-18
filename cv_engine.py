"""CV 审核引擎 — YOLO 推理 + 规则判断 + 证据帧采集"""
from pathlib import Path
from typing import Any


class CVEngine:
    """封装 YOLO 模型加载、推理、审核规则评估"""

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model_name = model_path.name
        self._model = None
        # TODO: 团队成员实现 — 加载 YOLO 模型
        # self._model = YOLO(str(model_path)) if model_path.exists() else None

    def is_ready(self) -> bool:
        """模型是否加载成功"""
        # TODO: 团队成员实现
        return self._model is not None or self.model_path.exists()

    def detect_image(self, image_path: Path) -> list[dict]:
        """对单张图片进行 YOLO 推理，返回检测结果列表

        Returns:
            [{class_name, confidence, bbox: [x1,y1,x2,y2]}, ...]
        """
        # TODO: 团队成员实现
        return []

    def detect_video_frames(self, video_path: Path, interval_sec: float = 1.0) -> list[dict]:
        """对视频按时间间隔采样帧，逐帧 YOLO 推理

        Returns:
            [{frame_idx, time_sec, detections: [...]}, ...]
        """
        # TODO: 团队成员实现
        return []

    def evaluate_rules(self, detections: list[dict], rules: dict) -> dict:
        """根据审核规则评估检测结果

        Args:
            detections: 所有检测结果
            rules: 审核规则配置 dict

        Returns:
            {
                conclusion: "pass" | "review" | "reject",
                reason: str,
                risk_triggers: [...],
                evidence_frames: [...]
            }
        """
        # TODO: 团队成员实现
        return {"conclusion": "pass", "reason": "", "risk_triggers": [], "evidence_frames": []}
