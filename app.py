"""Day08 智能数字媒体内容审核系统 — Flask 主应用"""
from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

from cv_engine import CVEngine
from job_manager import JobManager

# ---- 初始化 ----
BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)

# 全局组件（启动时初始化）
cv = CVEngine(model_path=BASE_DIR / "models" / "yolo11n.pt")
jobs = JobManager(base_dir=BASE_DIR / "outputs")


# ========== 公共 API ==========

@app.route("/api/health")
def api_health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "model_ready": cv.is_ready(),
        "model_name": cv.model_name,
    })


@app.route("/api/jobs", methods=["POST"])
def api_create_job():
    """创建审核任务（上传素材 → 返回 job_id，异步处理）"""
    # TODO: 团队成员实现
    pass


@app.route("/api/jobs", methods=["GET"])
def api_list_jobs():
    """获取所有任务列表"""
    # TODO: 团队成员实现
    pass


@app.route("/api/jobs/<job_id>", methods=["GET"])
def api_get_job(job_id):
    """查询单个任务详情"""
    # TODO: 团队成员实现
    pass


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_delete_job(job_id):
    """删除任务（仅 completed/failed 可删）"""
    # TODO: 团队成员实现
    pass


# ========== 方向 A 专属 API ==========

@app.route("/api/jobs/<job_id>/analyze", methods=["POST"])
def api_analyze(job_id):
    """触发 CV 审核分析（异步）"""
    # TODO: 团队成员实现
    pass


@app.route("/api/jobs/<job_id>/review", methods=["PATCH"])
def api_review(job_id):
    """人工复核（修改审核结论 + 备注）"""
    # TODO: 团队成员实现
    pass


@app.route("/api/jobs/<job_id>/report", methods=["GET"])
def api_report(job_id):
    """获取审核报告 JSON"""
    # TODO: 团队成员实现
    pass


# ========== 前端页面 ==========

@app.route("/")
def index():
    """工作台首页"""
    # TODO: 团队成员实现
    return "Day08 智能内容审核工作台"


# ========== 启动 ==========

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7880)
    args = parser.parse_args()

    print(f"[Day08] 智能内容审核工作台启动: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)
