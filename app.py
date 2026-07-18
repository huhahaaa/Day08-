"""Day08 智能数字媒体内容审核系统 — Flask 主应用"""
import json
import shutil
from pathlib import Path
from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS

from cv_engine import CVEngine
from job_manager import JobManager

# ---- 初始化 ----
BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 全局组件（启动时初始化）
cv = CVEngine(model_path=BASE_DIR / "models" / "yolo11n.pt")
jobs = JobManager(base_dir=BASE_DIR / "outputs")

# 加载默认规则
RULES_PATH = BASE_DIR / "default_rules.json"
if RULES_PATH.exists():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        DEFAULT_RULES = json.load(f)
else:
    DEFAULT_RULES = {
        "risk_classes": ["person", "car", "truck", "bus"],
        "reject_confidence": 0.60,
        "review_confidence": 0.35,
        "min_evidence_frames": 1
    }


# ========== 公共 API ==========

@app.route("/api/health")
def api_health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "model_ready": cv.is_ready(),
        "model_name": cv.model_name,
        "model_names": cv.model_names,
        "extra_model_errors": cv.extra_model_errors,
    })


@app.route("/api/jobs", methods=["POST"])
def api_create_job():
    """创建审核任务（上传素材 → 返回 job_id，异步处理）"""
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "没有文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "error": "文件名为空"}), 400
    filename = Path(file.filename).name

    # 保存上传文件到临时目录
    upload_dir = BASE_DIR / "uploads"
    upload_dir.mkdir(exist_ok=True)
    temp_path = upload_dir / filename
    file.save(str(temp_path))

    # 创建任务
    project_name = request.form.get("project_name", "审核任务")
    job = jobs.create_job(temp_path, project_name, DEFAULT_RULES)

    # 将任务状态改为 queued（等待处理）
    jobs.update_status(job["job_id"], "queued")

    return jsonify({
        "ok": True,
        "job_id": job["job_id"],
        "status": "queued"
    }), 202


@app.route("/api/jobs", methods=["GET"])
def api_list_jobs():
    """获取所有任务列表"""
    return jsonify(jobs.list_jobs())


@app.route("/api/jobs/<job_id>", methods=["GET"])
def api_get_job(job_id):
    """查询单个任务详情"""
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "任务不存在"}), 404
    return jsonify(job)


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_delete_job(job_id):
    """删除任务（仅 completed/failed 可删）"""
    success = jobs.delete_job(job_id)
    if not success:
        return jsonify({"ok": False, "error": "任务不存在或状态不允许删除"}), 400
    return jsonify({"ok": True})


# ========== 方向 A 专属 API ==========

import threading

def _run_analysis(job_id: str):
    """后台执行 CV 分析，完成后自动写入结果。"""
    try:
        input_path = jobs.get_input_path(job_id)
        if not input_path or not input_path.exists():
            raise Exception("找不到输入文件")

        job = jobs.get_job(job_id)
        settings = job.get("settings", DEFAULT_RULES) if job else DEFAULT_RULES
        result = cv.analyze_asset(input_path, jobs.get_job_dir(job_id), settings)
        result["job_id"] = job_id
        jobs.save_result(job_id, result)
        jobs.update_status(job_id, "completed")
    except Exception as e:
        jobs.update_status(job_id, "failed", str(e))


@app.route("/api/jobs/<job_id>/analyze", methods=["POST"])
def api_analyze(job_id):
    """触发 CV 审核分析（异步后台线程，立即返回）"""
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "任务不存在"}), 404

    if job.get("status") in ["running", "completed"]:
        return jsonify({"ok": False, "error": "任务正在处理或已完成"}), 400

    jobs.update_status(job_id, "running")
    threading.Thread(target=_run_analysis, args=(job_id,), daemon=True).start()

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "status": "running",
    }), 202


@app.route("/api/jobs/<job_id>/review", methods=["PATCH"])
def api_review(job_id):
    """人工复核（修改审核结论 + 备注）"""
    data = request.json or {}
    conclusion = data.get("verdict")
    note = data.get("note", "")
    reviewer = data.get("reviewer", "")

    if conclusion not in ["pass", "review", "reject"]:
        return jsonify({"ok": False, "error": "结论必须是 pass/review/reject"}), 400

    success = jobs.apply_review(job_id, conclusion, note, reviewer)
    if not success:
        return jsonify({"ok": False, "error": "任务不存在或状态不允许复核"}), 400

    return jsonify({"ok": True, "job_id": job_id, "verdict": conclusion})


@app.route("/api/jobs/<job_id>/report", methods=["GET"])
def api_report(job_id):
    """获取审核报告 JSON"""
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "任务不存在"}), 404

    report_path = jobs.get_report_path(job_id)
    if not report_path.exists():
        return jsonify({"ok": False, "error": "报告不存在"}), 404

    if request.args.get("download") == "1":
        return send_file(report_path, as_attachment=True, download_name=f"{job_id}_analysis_report.json")

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    return jsonify({"ok": True, "report": report})


@app.route("/api/jobs/<job_id>/input/<asset_name>", methods=["GET"])
def api_input_file(job_id, asset_name):
    """预览原始素材（图片或视频）"""
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "任务不存在"}), 404
    file_path = jobs.get_job_dir(job_id) / "input" / asset_name
    if not file_path.exists():
        return jsonify({"ok": False, "error": "文件不存在"}), 404

    # 视频需要 Range 请求支持（206 Partial Content），否则浏览器无法拖动进度条
    suffix = file_path.suffix.lower()
    if suffix in {".mp4", ".webm", ".ogg"}:
        return send_file(file_path, mimetype=f"video/{suffix[1:]}", conditional=True)
    if suffix in {".mkv"}:
        return send_file(file_path, mimetype="video/x-matroska", conditional=True)
    if suffix in {".avi"}:
        return send_file(file_path, mimetype="video/x-msvideo", conditional=True)
    if suffix in {".mov"}:
        return send_file(file_path, mimetype="video/quicktime", conditional=True)
    return send_file(file_path)


@app.route("/api/jobs/<job_id>/evidence/<fname>", methods=["GET"])
def api_evidence_file(job_id, fname):
    """查看单张证据图片"""
    evidence_dir = jobs.get_evidence_dir(job_id)
    file_path = evidence_dir / fname
    if not file_path.exists():
        return jsonify({"ok": False, "error": "证据文件不存在"}), 404
    return send_file(file_path)


@app.route("/api/jobs/<job_id>/evidence", methods=["GET"])
def api_evidence(job_id):
    """下载证据帧（打包为 zip）"""
    evidence_dir = jobs.get_evidence_dir(job_id)
    if not evidence_dir.exists() or not list(evidence_dir.iterdir()):
        return jsonify({"ok": False, "error": "没有证据文件"}), 404

    import zipfile
    zip_path = jobs.get_job_dir(job_id) / f"{job_id}_evidence.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for f in evidence_dir.iterdir():
            zf.write(f, f.name)

    return send_file(zip_path, as_attachment=True, download_name=f"{job_id}_evidence.zip")


# ========== 前端页面 ==========

@app.route("/")
def index():
    """工作台首页"""
    return render_template("index.html")


# ========== 启动 ==========

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7880)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"[Day08] 智能内容审核工作台启动: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
