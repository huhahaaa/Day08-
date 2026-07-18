"""任务管理器：任务 CRUD + JSON 持久化 + 状态机"""
from __future__ import annotations

import json
import shutil
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

    def _get_job_dir(self, job_id: str) -> Path:
        return self.base_dir / job_id

    def get_job_dir(self, job_id: str) -> Path:
        """获取任务目录。"""
        return self._get_job_dir(job_id)

    def _get_job_path(self, job_id: str) -> Path:
        return self._get_job_dir(job_id) / "job.json"

    def create_job(self, asset_path: Path, project_name: str, settings: dict = None) -> dict:
        """创建任务 → 返回 job 对象（立即返回，不阻塞）"""
        job_id = self.generate_job_id()
        job_dir = self._get_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        # 保存输入文件
        input_dir = job_dir / "input"
        input_dir.mkdir(exist_ok=True)
        dest_path = input_dir / asset_path.name
        shutil.copy2(asset_path, dest_path)

        now = datetime.now().isoformat()
        job = {
            "job_id": job_id,
            "project_name": project_name,
            "asset_name": asset_path.name,
            "status": "created",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "settings": settings or {},
            "result_file": None,
            "error": None,
            "verdict": None,      # 最终结论: pass / review / reject
            "review": None,       # 人工复核记录
        }

        self._save_job(job_id, job)
        return job

    def get_job(self, job_id: str) -> Optional[dict]:
        """读取单个任务"""
        job_path = self._get_job_path(job_id)
        if not job_path.exists():
            return None
        with open(job_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_jobs(self) -> list[dict]:
        """列出所有任务"""
        jobs = []
        for job_dir in self.base_dir.iterdir():
            if job_dir.is_dir():
                job_path = job_dir / "job.json"
                if job_path.exists():
                    with open(job_path, "r", encoding="utf-8") as f:
                        jobs.append(json.load(f))
        # 按创建时间倒序
        return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_job(self, job_id: str) -> bool:
        """删除任务（仅 completed/failed 可删）"""
        job = self.get_job(job_id)
        if not job:
            return False
        status = job.get("status")
        if status not in ["completed", "failed"]:
            return False
        shutil.rmtree(self._get_job_dir(job_id))
        return True

    def update_status(self, job_id: str, status: str, error: str = None) -> bool:
        """更新任务状态"""
        if status not in STATES:
            return False
        job = self.get_job(job_id)
        if not job:
            return False

        job["status"] = status
        now = datetime.now().isoformat()
        if status == "running" and job.get("started_at") is None:
            job["started_at"] = now
        if status in ["completed", "failed"]:
            job["completed_at"] = now
        if error:
            job["error"] = error
        elif status in ["queued", "running", "completed"]:
            job["error"] = None

        self._save_job(job_id, job)
        return True

    def save_result(self, job_id: str, result: dict) -> bool:
        """保存分析结果"""
        job = self.get_job(job_id)
        if not job:
            return False

        result_path = self._get_job_dir(job_id) / "analysis_report.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        job["result"] = result
        job["result_file"] = "analysis_report.json"
        job["verdict"] = self._extract_verdict(result)
        job["error"] = None
        self._save_job(job_id, job)
        return True

    def apply_review(self, job_id: str, conclusion: str, note: str = "", reviewer: str = "") -> bool:
        """写入人工复核结果，同步更新 analysis_report.json"""
        if conclusion not in ["pass", "review", "reject"]:
            return False
        job = self.get_job(job_id)
        if not job:
            return False

        job["review"] = {
            "original_verdict": job.get("verdict"),
            "new_verdict": conclusion,
            "note": note,
            "reviewer": reviewer or "anonymous",
            "reviewed_at": datetime.now().isoformat()
        }
        job["verdict"] = conclusion  # 更新最终结论
        self._save_job(job_id, job)

        # 同步写回 analysis_report.json，保证 /report 接口读到最新结论
        report_path = self._get_job_dir(job_id) / "analysis_report.json"
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            report["review"]["manual_conclusion"] = conclusion
            report["review"]["reviewer"] = reviewer or "anonymous"
            report["review"]["note"] = note
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

        return True

    def get_input_path(self, job_id: str) -> Optional[Path]:
        """获取任务的输入文件路径"""
        job = self.get_job(job_id)
        if not job:
            return None
        input_dir = self._get_job_dir(job_id) / "input"
        files = list(input_dir.iterdir())
        return files[0] if files else None

    def get_evidence_dir(self, job_id: str) -> Path:
        """获取证据帧目录"""
        return self._get_job_dir(job_id) / "evidence"

    def get_report_path(self, job_id: str) -> Path:
        """获取分析报告路径"""
        return self._get_job_dir(job_id) / "analysis_report.json"

    def _save_job(self, job_id: str, data: dict):
        """保存任务 JSON"""
        job_path = self._get_job_path(job_id)
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _extract_verdict(result: dict) -> Optional[str]:
        """从 CV 报告中提取最终机器结论。"""
        if result.get("verdict") in ["pass", "review", "reject"]:
            return result["verdict"]
        if result.get("conclusion") in ["pass", "review", "reject"]:
            return result["conclusion"]

        review = result.get("review") or {}
        conclusion = review.get("machine_conclusion")
        if conclusion in ["pass", "review", "reject"]:
            return conclusion
        return None

    @staticmethod
    def generate_job_id() -> str:
        """生成唯一任务 ID"""
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"{now}_{suffix}"
