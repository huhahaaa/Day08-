# YOLO 模块技术实现方案

## 1. 负责范围

本模块负责方向 A“智能数字媒体内容审核系统”中的 CV 算法部分，核心目标是完成：

```text
图片/视频素材
    -> OpenCV 读取和采样
    -> YOLO 目标检测
    -> 检测结果结构化
    -> 审核规则判断
    -> 证据帧保存
    -> analysis_report.json 输出
```

本模块不直接负责 Flask 路由、任务 CRUD、前端页面渲染和人工复核页面，但需要给后端和前端提供稳定的数据结构。

## 2. 技术栈

| 技术 | 用途 |
|---|---|
| Ultralytics YOLO | 加载 `models/yolo11n.pt` 并执行目标检测 |
| OpenCV | 图片读取、视频采样、证据帧绘制和保存 |
| JSON | 保存检测结果和审核报告 |
| pathlib | 统一处理 Windows 路径 |

依赖已经写入 `requirements.txt`：

```text
ultralytics>=8.0
opencv-python>=4.8
numpy>=1.24
Pillow>=10.0
```

## 3. 输入输出约定

### 3.1 输入文件

支持格式建议如下：

```text
图片：jpg、jpeg、png、bmp、webp
视频：mp4、avi、mov、mkv
```

后端上传完成后，应将原始素材放入任务目录：

```text
outputs/<job_id>/input/<asset_name>
```

YOLO 模块从该路径读取素材。

### 3.2 规则配置

默认读取项目根目录下的 `default_rules.json`：

```json
{
  "risk_classes": ["knife", "scissors", "baseball bat"],
  "warning_classes": ["bottle", "wine glass", "cell phone"],
  "reject_confidence": 0.60,
  "review_confidence": 0.35,
  "min_evidence_frames": 1,
  "video_sample_interval_sec": 1.0
}
```

含义：

| 字段 | 说明 |
|---|---|
| `risk_classes` | 命中后可能直接不通过的高风险类别 |
| `warning_classes` | 命中后建议待复核的提醒类别 |
| `reject_confidence` | 高风险类别达到该置信度时判定不通过 |
| `review_confidence` | 达到该置信度但不足以不通过时判定待复核 |
| `min_evidence_frames` | 至少保存的证据帧数量 |
| `video_sample_interval_sec` | 视频采样间隔，默认每 1 秒采一帧 |

## 4. 模块接口设计

当前项目已有 `cv_engine.py`，建议围绕 `CVEngine` 完成实现。

```python
class CVEngine:
    def __init__(self, model_path: Path):
        ...

    def is_ready(self) -> bool:
        ...

    def detect_image(self, image_path: Path) -> list[dict]:
        ...

    def detect_video_frames(self, video_path: Path, interval_sec: float = 1.0) -> list[dict]:
        ...

    def evaluate_rules(self, detections: list[dict], rules: dict) -> dict:
        ...
```

建议额外补充两个内部工具方法：

```python
def draw_evidence(image, detections: list[dict], output_path: Path) -> str:
    """绘制检测框并保存证据图，返回证据图相对路径"""

def analyze_asset(asset_path: Path, job_dir: Path, rules: dict) -> dict:
    """统一处理图片/视频，生成完整 analysis_report.json 数据"""
```

## 5. 模型加载方案

### 5.1 加载逻辑

启动 Flask 时初始化：

```python
cv = CVEngine(model_path=BASE_DIR / "models" / "yolo11n.pt")
```

实现要求：

1. 判断模型文件是否存在；
2. 存在则调用 `YOLO(str(model_path))` 加载；
3. 加载失败时记录错误，不让 Flask 进程直接崩溃；
4. `/api/health` 通过 `cv.is_ready()` 返回模型状态。

建议实现：

```python
from ultralytics import YOLO

class CVEngine:
    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.model_name = self.model_path.name
        self._model = None
        self.load_error = None

        if not self.model_path.exists():
            self.load_error = f"模型文件不存在: {self.model_path}"
            return

        try:
            self._model = YOLO(str(self.model_path))
        except Exception as exc:
            self.load_error = str(exc)

    def is_ready(self) -> bool:
        return self._model is not None
```

## 6. 图片检测流程

### 6.1 处理步骤

```text
校验图片路径
    -> OpenCV 读取图片
    -> 调用 YOLO 推理
    -> 提取 class_name、confidence、bbox
    -> 返回检测列表
```

### 6.2 输出结构

单张图片检测输出：

```json
[
  {
    "class_id": 0,
    "class_name": "person",
    "confidence": 0.82,
    "bbox": [120, 80, 300, 420]
  }
]
```

字段说明：

| 字段 | 说明 |
|---|---|
| `class_id` | YOLO 类别编号 |
| `class_name` | 类别名称 |
| `confidence` | 置信度，保留 4 位小数 |
| `bbox` | 检测框坐标 `[x1, y1, x2, y2]`，整数 |

## 7. 视频检测流程

### 7.1 采样策略

视频不逐帧检测，避免处理过慢。使用 OpenCV 每隔固定秒数采样一帧：

```text
fps = cap.get(cv2.CAP_PROP_FPS)
interval_frames = max(1, int(fps * interval_sec))
```

默认：

```text
interval_sec = 1.0
```

即每秒采一帧。

### 7.2 处理步骤

```text
打开视频
    -> 获取 fps、总帧数、时长
    -> 按 interval_sec 采样
    -> 对采样帧执行 YOLO
    -> 保存每个采样帧的检测结果
    -> 对命中风险/提醒类别的帧保存证据图
```

### 7.3 输出结构

视频采样帧检测输出：

```json
[
  {
    "frame_index": 60,
    "time_sec": 2.0,
    "detections": [
      {
        "class_id": 43,
        "class_name": "knife",
        "confidence": 0.76,
        "bbox": [150, 90, 260, 360]
      }
    ]
  }
]
```

## 8. 审核规则实现

### 8.1 判断优先级

审核结论分为：

```text
pass   -> 通过
review -> 待复核
reject -> 不通过
```

优先级：

```text
reject > review > pass
```

规则：

```text
1. class_name 属于 risk_classes，且 confidence >= reject_confidence
   -> reject

2. class_name 属于 risk_classes，且 confidence >= review_confidence
   -> review

3. class_name 属于 warning_classes，且 confidence >= review_confidence
   -> review

4. 没有命中风险或提醒类别
   -> pass
```

### 8.2 返回结构

```json
{
  "conclusion": "reject",
  "conclusion_text": "不通过",
  "reason": "检测到高风险类别 knife，最高置信度 0.76，超过不通过阈值 0.60",
  "risk_triggers": [
    {
      "class_name": "knife",
      "confidence": 0.76,
      "frame_index": 60,
      "time_sec": 2.0,
      "level": "reject"
    }
  ],
  "evidence_frames": [
    "keyframes/frame_000060.jpg"
  ]
}
```

## 9. 证据帧保存方案

### 9.1 保存目录

```text
outputs/<job_id>/keyframes/
```

### 9.2 命名规则

图片证据：

```text
image_evidence.jpg
```

视频证据：

```text
frame_000060.jpg
```

### 9.3 绘制要求

证据图需要包含：

```text
检测框
类别名
置信度
```

颜色建议：

| 类型 | 颜色 |
|---|---|
| 高风险类别 | 红色 |
| 提醒类别 | 黄色 |
| 其他类别 | 绿色 |

OpenCV 绘制：

```python
cv2.rectangle(...)
cv2.putText(...)
cv2.imwrite(...)
```

## 10. 最终报告结构

YOLO 模块最终需要向后端输出 `analysis_report.json`：

```json
{
  "job_id": "20260718_101530_a1b2c3d4",
  "asset_name": "demo.mp4",
  "media_type": "video",
  "model_name": "yolo11n.pt",
  "rules": {
    "risk_classes": ["knife", "scissors", "baseball bat"],
    "warning_classes": ["bottle", "wine glass", "cell phone"],
    "reject_confidence": 0.6,
    "review_confidence": 0.35,
    "video_sample_interval_sec": 1.0
  },
  "review": {
    "machine_conclusion": "reject",
    "machine_conclusion_text": "不通过",
    "manual_conclusion": null,
    "reviewer": "",
    "note": ""
  },
  "summary": {
    "sampled_frames": 8,
    "total_detections": 12,
    "risk_hits": 2,
    "warning_hits": 1,
    "max_confidence": 0.76
  },
  "frames": [
    {
      "frame_index": 60,
      "time_sec": 2.0,
      "detections": [
        {
          "class_id": 43,
          "class_name": "knife",
          "confidence": 0.76,
          "bbox": [150, 90, 260, 360]
        }
      ],
      "evidence_image": "keyframes/frame_000060.jpg"
    }
  ],
  "evidence_frames": [
    "keyframes/frame_000060.jpg"
  ],
  "created_at": "2026-07-18T10:30:00"
}
```

## 11. 异常处理

YOLO 模块必须明确抛出或返回以下错误：

| 场景 | 错误信息 |
|---|---|
| 模型文件不存在 | `模型文件不存在` |
| 模型加载失败 | `模型加载失败: xxx` |
| 输入文件不存在 | `输入文件不存在` |
| 图片无法读取 | `图片读取失败或文件损坏` |
| 视频无法打开 | `视频读取失败或格式不支持` |
| 视频 FPS 异常 | `视频 FPS 无效` |
| 没有采样到有效帧 | `视频没有可分析帧` |
| YOLO 推理异常 | `YOLO 推理失败: xxx` |

这些错误最终由后端写入 `job.json.error`，并将任务状态改为 `failed`。

## 12. 性能控制

为了保证课堂项目可运行，建议：

1. 视频默认每 1 秒采样 1 帧；
2. 最多采样 120 帧，防止长视频卡死；
3. 推理图片尺寸使用 YOLO 默认设置即可；
4. 首次加载模型放在服务启动阶段，避免每个任务重复加载；
5. 证据帧最多保存 10 张，避免输出目录过大。

可配置参数建议：

```json
{
  "video_sample_interval_sec": 1.0,
  "max_sample_frames": 120,
  "max_evidence_frames": 10
}
```

## 13. 与后端联调点

后端调用 YOLO 模块时建议流程：

```python
rules = load_json(BASE_DIR / "default_rules.json")
report = cv.analyze_asset(asset_path, job_dir, rules)
save_json(job_dir / "analysis_report.json", report)
```

后端需要保证：

```text
1. 传入真实存在的素材路径；
2. 传入任务目录 job_dir；
3. 任务开始前创建 keyframes、result 等目录；
4. YOLO 异常时捕获错误并更新 job.json；
5. 分析成功后将 job.json.result_file 设置为 analysis_report.json。
```

## 14. 测试方案

### 14.1 正常测试

| 编号 | 测试内容 | 预期 |
|---|---|---|
| CV-001 | 检测一张正常 JPG 图片 | 返回 detections 列表 |
| CV-002 | 检测一段正常 MP4 视频 | 返回采样帧列表 |
| CV-003 | 图片中命中高风险类别且置信度超过 0.60 | 结论为 `reject` |
| CV-004 | 图片中命中提醒类别且置信度超过 0.35 | 结论为 `review` |
| CV-005 | 未命中规则类别 | 结论为 `pass` |

### 14.2 异常测试

| 编号 | 测试内容 | 预期 |
|---|---|---|
| CV-101 | 删除或改名 `models/yolo11n.pt` 后启动 | `model_ready=false` |
| CV-102 | 传入不存在的图片路径 | 报错 `输入文件不存在` |
| CV-103 | 传入空文件 | 报错 `图片读取失败或文件损坏` |
| CV-104 | 传入 txt 伪装文件 | 报错 `格式不支持` 或读取失败 |
| CV-105 | 传入损坏视频 | 报错 `视频读取失败或格式不支持` |

## 15. 个人交付物

作为 YOLO/CV 负责人，最终建议提交：

```text
1. cv_engine.py 中 YOLO 加载、图片检测、视频采样、规则判断代码；
2. default_rules.json 规则说明；
3. 一份 YOLO 技术实现方案，即本文档；
4. 至少 2 张证据帧截图；
5. 一份 analysis_report.json 示例；
6. 至少 3 条 CV 模块测试记录；
7. 至少 1 条与 YOLO 相关的 Bug 记录。
```

## 16. 开发优先级

必须先完成：

```text
模型加载
-> 图片检测
-> 规则判断
-> 证据图保存
-> analysis_report.json
```

然后完成：

```text
视频采样检测
-> 多证据帧
-> 异常处理
-> 测试记录
```

最后再做：

```text
阈值可配置
证据帧数量限制
CSV/ZIP 导出支持
更多类别规则
```

