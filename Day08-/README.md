# Day08 智能数字媒体内容审核系统

CV 综合项目实战 — 方向 A：智能数字媒体内容审核系统

## 技术栈

Python · Flask · YOLO (Ultralytics) · OpenCV · HTML/CSS/JavaScript

## 运行

```bash
conda activate yolo
pip install -r requirements.txt
python app.py --host 127.0.0.1 --port 7880
```

浏览器打开 http://127.0.0.1:7880

## 项目结构

```
Day08-/
├── app.py              # Flask 主应用
├── requirements.txt
├── models/             # YOLO 模型文件
├── assets/             # 测试素材
├── outputs/            # 任务输出（按 job_id 分目录）
├── static/             # 前端静态资源
├── templates/          # HTML 模板
├── tests/              # 测试脚本
└── docs/               # 文档
```
