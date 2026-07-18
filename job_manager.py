"""任务管理器 — 任务 CRUD + JSON 持久化 + 状态机"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

STATES = ["created", "queued", "running", "completed", "failed"]


class JobManager:
    """管理审核任务的生命周期"""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ---- 任务 CRUD ----

    def create_job(self, asset_path: Path, project_name: str, settings: dict = None) -> dict:
        """创建任务 → 返回 job 对象（立即返回，不阻塞）"""
        # TODO: 团队成员实现
        pass

    def get_job(self, job_id: str) -> Optional[dict]:
        """读取单个任务"""
        # TODO: 团队成员实现
        pass

    def list_jobs(self) -> list[dict]:
        """列出所有任务"""
        # TODO: 团队成员实现
        pass

    def delete_job(self, job_id: str) -> bool:
        """删除任务（仅 completed/failed 可删）"""
        # TODO: 团队成员实现
        pass

    def update_status(self, job_id: str, status: str, error: str = None) -> bool:
        """更新任务状态"""
        # TODO: 团队成员实现
        pass

    # ---- 人工复核 ----

    def apply_review(self, job_id: str, conclusion: str, note: str = "", reviewer: str = "") -> bool:
        """写入人工复核结果"""
        # TODO: 团队成员实现
        pass

    # ---- 工具 ----

    @staticmethod
    def generate_job_id() -> str:
        """生成唯一任务 ID"""
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"{now}_{suffix}"

    @staticmethod
    def job_template(job_id: str, project_name: str, asset_name: str) -> dict:
        """新建任务的 JSON 模板"""
        now = datetime.now().isoformat()
        return {
            "job_id": job_id,
            "project_name": project_name,
            "asset_name": asset_name,
            "status": "created",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "settings": {},
            "result_file": None,
            "error": None,
        }
