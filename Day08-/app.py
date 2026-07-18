"""Day08 智能数字媒体内容审核系统 — Flask 主应用"""
import json
import shutil
import zipfile
from pathlib import Path
from flask import Flask, jsonify, request, send_file, render_template, send_from_directory
from flask_cors import CORS
import cv2
import numpy as np

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
    })


@app.route("/api/jobs", methods=["POST"])
def api_create_job():
    """创建审核任务（上传素材 → 返回 job_id，异步处理）"""
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "没有文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "error": "文件名为空"}), 400

    # 检查文件扩展名
    allowed_ext = {'.jpg', '.jpeg', '.png', '.mp4', '.avi', '.mov', '.mkv'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        return jsonify({"ok": False, "error": f"不支持的文件格式: {ext}"}), 400

    # 检查文件大小（非空）
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size == 0:
        return jsonify({"ok": False, "error": "文件为空"}), 400

    # 保存上传文件到临时目录
    upload_dir = BASE_DIR / "uploads"
    upload_dir.mkdir(exist_ok=True)
    temp_path = upload_dir / file.filename
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

@app.route("/api/jobs/<job_id>/analyze", methods=["POST"])
def api_analyze(job_id):
    """触发 CV 审核分析（异步）"""
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "任务不存在"}), 404

    if job.get("status") in ["running", "completed"]:
        return jsonify({"ok": False, "error": "任务正在处理或已完成"}), 400

    # 检查模型是否就绪
    if not cv.is_ready():
        return jsonify({"ok": False, "error": "模型未加载，请检查模型文件是否存在"}), 500

    # 更新状态为运行中
    jobs.update_status(job_id, "running")

    try:
        # 获取输入文件
        input_path = jobs.get_input_path(job_id)
        if not input_path or not input_path.exists():
            raise Exception("找不到输入文件")

        # 判断文件类型
        ext = input_path.suffix.lower()
        settings = job.get("settings", DEFAULT_RULES)
        result = None
        evidence_filenames = []

        if ext in ['.jpg', '.jpeg', '.png']:
            # ---------- 图片审核 ----------
            detections = cv.detect_image(input_path)
            result = cv.evaluate_rules(detections, settings)

            # 绘制证据帧
            evidence_dir = jobs.get_evidence_dir(job_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            # 生成唯一文件名
            filename = f"evidence_{job_id}.jpg"
            evidence_path = evidence_dir / filename
            cv.draw_boxes(input_path, detections, evidence_path)
            evidence_filenames = [filename]  # 存储文件名（相对路径）

        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            # ---------- 视频审核 ----------
            # 执行帧检测（返回每帧的检测结果列表）
            frame_results = cv.detect_video_frames(input_path, interval_sec=1.0, max_frames=30)
            # 评估整体结果
            result = cv.evaluate_rules(frame_results, settings)

            # 保存证据帧（最多保存5帧）
            evidence_dir = jobs.get_evidence_dir(job_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            cap = cv2.VideoCapture(str(input_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 选取要保存的帧索引（取前5个有检测结果的帧，或前5个采样帧）
            saved_count = 0
            # 如果有检测结果，优先保存有目标的帧，否则保存前5个采样帧
            frames_with_detections = [fr for fr in frame_results if fr.get('detections')]
            selected_frames = frames_with_detections[:5] if frames_with_detections else frame_results[:5]

            for idx, fr in enumerate(selected_frames):
                frame_num = fr['frame']
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if not ret:
                    continue
                # 对当前帧进行检测（用于绘制框）
                dets = cv.detect_frame(frame)
                # 绘制框
                draw_img = cv.draw_boxes_on_frame(frame, dets)  # 需要新增方法
                # 保存
                filename = f"frame_{idx}_{job_id}.jpg"
                save_path = evidence_dir / filename
                cv2.imwrite(str(save_path), draw_img)
                evidence_filenames.append(filename)
                saved_count += 1
                if saved_count >= 5:
                    break
            cap.release()
            result["evidence_frames"] = evidence_filenames  # 存储文件名列表

        else:
            raise Exception(f"不支持的文件类型: {ext}")

        # 统一处理证据路径（向后兼容）
        if evidence_filenames:
            result["evidence_path"] = evidence_filenames[0]  # 保留第一张作为主证据
        result["evidence_filenames"] = evidence_filenames  # 全部文件名

        # 保存结果
        jobs.save_result(job_id, result)
        jobs.update_status(job_id, "completed")

        return jsonify({
            "ok": True,
            "job_id": job_id,
            "status": "completed",
            "verdict": result.get("verdict", "unknown")
        })

    except Exception as e:
        jobs.update_status(job_id, "failed", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


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

    report = {
        "job_id": job_id,
        "asset_name": job.get("asset_name"),
        "status": job.get("status"),
        "verdict": job.get("verdict"),
        "result": job.get("result"),
        "review": job.get("review"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at")
    }

    # 保存报告文件
    report_dir = jobs._get_job_dir(job_id)
    report_path = report_dir / "report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return send_file(report_path, as_attachment=True, download_name=f"{job_id}_report.json")


@app.route("/api/jobs/<job_id>/evidence", methods=["GET"])
def api_evidence(job_id):
    """下载证据帧（打包为 zip）"""
    evidence_dir = jobs.get_evidence_dir(job_id)
    if not evidence_dir.exists() or not list(evidence_dir.iterdir()):
        return jsonify({"ok": False, "error": "没有证据文件"}), 404

    zip_path = jobs._get_job_dir(job_id) / f"{job_id}_evidence.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for f in evidence_dir.iterdir():
            zf.write(f, f.name)
    return send_file(zip_path, as_attachment=True, download_name=f"{job_id}_evidence.zip")


# ========== 新增：证据图片访问路由 ==========
@app.route("/api/jobs/<job_id>/evidence/<filename>")
def get_evidence_file(job_id, filename):
    """获取单张证据图片"""
    evidence_dir = jobs.get_evidence_dir(job_id)
    return send_from_directory(evidence_dir, filename)


# ========== 新增：原始素材访问路由 ==========
@app.route("/api/jobs/<job_id>/input/<filename>")
def get_input_file(job_id, filename):
    """获取原始素材（用于预览）"""
    input_dir = jobs._get_job_dir(job_id) / "input"
    return send_from_directory(input_dir, filename)


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
    args = parser.parse_args()

    print(f"[Day08] 智能内容审核工作台启动: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)