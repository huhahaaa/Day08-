# 模型自动审核规则判断技术方案

## 1. 模块定位

“审核规则判断”位于 YOLO 检测之后，负责把模型输出的目标检测结果转换成业务审核结论。

流程位置：

```text
YOLO 检测结果
    -> 审核规则判断
    -> 自动结论：通过 / 待复核 / 不通过
    -> 风险原因
    -> 证据帧列表
    -> analysis_report.json
```

该模块不重新推理模型，只消费 YOLO 已经输出的检测结果。

## 2. 输入数据

审核规则判断模块接收两类输入：

### 2.1 检测结果 detections

图片检测结果：

```json
[
  {
    "class_id": 43,
    "class_name": "knife",
    "confidence": 0.76,
    "bbox": [150, 90, 260, 360],
    "evidence_image": "keyframes/image_evidence.jpg"
  }
]
```

视频检测结果：

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
    ],
    "evidence_image": "keyframes/frame_000060.jpg"
  }
]
```

为了让图片和视频共用一套审核逻辑，建议先统一展开成 `flat_detections`：

```json
[
  {
    "media_type": "video",
    "frame_index": 60,
    "time_sec": 2.0,
    "class_name": "knife",
    "confidence": 0.76,
    "bbox": [150, 90, 260, 360],
    "evidence_image": "keyframes/frame_000060.jpg"
  }
]
```

### 2.2 审核规则 rules

来自 `default_rules.json`：

```json
{
  "risk_classes": ["knife", "scissors", "baseball bat"],
  "warning_classes": ["bottle", "wine glass", "cell phone"],
  "reject_confidence": 0.60,
  "review_confidence": 0.35,
  "min_evidence_frames": 1
}
```

## 3. 输出数据

审核规则判断模块返回：

```json
{
  "conclusion": "reject",
  "conclusion_text": "不通过",
  "reason": "检测到高风险类别 knife，最高置信度 0.76，超过不通过阈值 0.60",
  "risk_level": "high",
  "risk_triggers": [
    {
      "class_name": "knife",
      "confidence": 0.76,
      "frame_index": 60,
      "time_sec": 2.0,
      "level": "reject",
      "evidence_image": "keyframes/frame_000060.jpg"
    }
  ],
  "evidence_frames": [
    "keyframes/frame_000060.jpg"
  ],
  "summary": {
    "total_detections": 12,
    "risk_hits": 2,
    "warning_hits": 1,
    "max_confidence": 0.76
  }
}
```

## 4. 自动审核结论

系统只输出三种机器结论：

| 机器结论 | 中文展示 | 含义 |
|---|---|---|
| `pass` | 通过 | 未发现规则关注目标，或置信度低于复核阈值 |
| `review` | 待复核 | 存在可疑目标，但证据不足以直接不通过 |
| `reject` | 不通过 | 命中高风险类别且置信度达到不通过阈值 |

结论优先级：

```text
reject > review > pass
```

只要任意一条检测结果触发 `reject`，最终结论就是 `reject`。

## 5. 规则判断细则

### 5.1 高风险类别直接不通过

条件：

```text
class_name in risk_classes
confidence >= reject_confidence
```

结论：

```text
reject / 不通过
```

示例：

```json
{
  "class_name": "knife",
  "confidence": 0.76
}
```

如果 `reject_confidence = 0.60`，则该检测结果触发不通过。

### 5.2 高风险类别低置信度待复核

条件：

```text
class_name in risk_classes
review_confidence <= confidence < reject_confidence
```

结论：

```text
review / 待复核
```

原因：模型识别到了高风险类别，但置信度不足以直接拒绝，需要人工确认。

### 5.3 提醒类别待复核

条件：

```text
class_name in warning_classes
confidence >= review_confidence
```

结论：

```text
review / 待复核
```

提醒类别不直接判定不通过，除非项目 PRD 另行规定。

### 5.4 无风险通过

条件：

```text
没有任何检测结果触发 reject 或 review
```

结论：

```text
pass / 通过
```

注意：`pass` 不等于“画面中没有任何目标”，而是“没有命中审核规则关注的目标”。

## 6. 多帧结果处理

视频会产生多帧检测结果。最终结论按最严重结果决定：

```text
任意帧触发 reject
    -> 全视频 reject

没有 reject，但任意帧触发 review
    -> 全视频 review

所有帧均未触发风险
    -> 全视频 pass
```

示例：

| 帧 | 检测结果 | 单帧结论 |
|---|---|---|
| 第 1 秒 | 无风险 | pass |
| 第 2 秒 | knife 0.76 | reject |
| 第 3 秒 | bottle 0.50 | review |

最终视频结论：

```text
reject
```

因为 `reject` 优先级最高。

## 7. 证据选择策略

证据帧不是保存所有帧，而是优先保存最有解释力的帧。

### 7.1 排序规则

触发项排序：

```text
1. reject 级别优先于 review
2. 同级别按 confidence 从高到低
3. 同置信度按 time_sec 从小到大
```

### 7.2 数量控制

建议：

```text
最少保存 min_evidence_frames 张
最多保存 10 张
```

配置字段：

```json
{
  "min_evidence_frames": 1,
  "max_evidence_frames": 10
}
```

如果当前项目没有 `max_evidence_frames`，代码中可以默认写死为 10。

## 8. 原因文案生成

自动审核结果需要给前端展示可读原因。

### 8.1 不通过原因

模板：

```text
检测到高风险类别 {class_name}，最高置信度 {confidence}，超过不通过阈值 {reject_confidence}
```

示例：

```text
检测到高风险类别 knife，最高置信度 0.76，超过不通过阈值 0.60
```

### 8.2 待复核原因

模板一，高风险低置信度：

```text
检测到疑似高风险类别 {class_name}，置信度 {confidence}，需要人工复核
```

模板二，提醒类别：

```text
检测到提醒类别 {class_name}，置信度 {confidence}，建议人工确认
```

### 8.3 通过原因

模板：

```text
未发现达到审核阈值的风险目标
```

## 9. 推荐代码结构

建议在 `cv_engine.py` 中实现：

```python
def evaluate_rules(self, detections: list[dict], rules: dict) -> dict:
    flat_items = self._flatten_detections(detections)
    triggers = self._collect_rule_triggers(flat_items, rules)
    conclusion = self._decide_conclusion(triggers)
    evidence_frames = self._select_evidence_frames(triggers, rules)
    summary = self._build_rule_summary(flat_items, triggers, rules)

    return {
        "conclusion": conclusion,
        "conclusion_text": self._conclusion_text(conclusion),
        "reason": self._build_reason(conclusion, triggers, rules),
        "risk_level": self._risk_level(conclusion),
        "risk_triggers": triggers,
        "evidence_frames": evidence_frames,
        "summary": summary,
    }
```

如果时间不够，也可以先写成一个函数，不拆私有方法。

## 10. 核心伪代码

```python
def evaluate_rules(detections, rules):
    risk_classes = set(rules.get("risk_classes", []))
    warning_classes = set(rules.get("warning_classes", []))
    reject_conf = float(rules.get("reject_confidence", 0.6))
    review_conf = float(rules.get("review_confidence", 0.35))

    flat_items = []

    for item in detections:
        if "detections" in item:
            # 视频帧结构
            for det in item.get("detections", []):
                flat_items.append({
                    **det,
                    "frame_index": item.get("frame_index"),
                    "time_sec": item.get("time_sec"),
                    "evidence_image": item.get("evidence_image"),
                })
        else:
            # 图片结构
            flat_items.append(item)

    triggers = []

    for det in flat_items:
        class_name = det.get("class_name")
        confidence = float(det.get("confidence", 0))

        if class_name in risk_classes and confidence >= reject_conf:
            triggers.append({
                **det,
                "level": "reject",
                "message": "高风险类别超过不通过阈值",
            })
        elif class_name in risk_classes and confidence >= review_conf:
            triggers.append({
                **det,
                "level": "review",
                "message": "疑似高风险类别，需要复核",
            })
        elif class_name in warning_classes and confidence >= review_conf:
            triggers.append({
                **det,
                "level": "review",
                "message": "提醒类别，需要复核",
            })

    if any(t["level"] == "reject" for t in triggers):
        conclusion = "reject"
    elif any(t["level"] == "review" for t in triggers):
        conclusion = "review"
    else:
        conclusion = "pass"

    triggers.sort(
        key=lambda x: (
            0 if x["level"] == "reject" else 1,
            -float(x.get("confidence", 0)),
            float(x.get("time_sec") or 0),
        )
    )

    evidence_frames = []
    for trigger in triggers:
        image = trigger.get("evidence_image")
        if image and image not in evidence_frames:
            evidence_frames.append(image)

    evidence_frames = evidence_frames[:10]

    return {
        "conclusion": conclusion,
        "conclusion_text": {
            "pass": "通过",
            "review": "待复核",
            "reject": "不通过",
        }[conclusion],
        "reason": build_reason(conclusion, triggers, rules),
        "risk_triggers": triggers,
        "evidence_frames": evidence_frames,
        "summary": {
            "total_detections": len(flat_items),
            "risk_hits": sum(1 for x in flat_items if x.get("class_name") in risk_classes),
            "warning_hits": sum(1 for x in flat_items if x.get("class_name") in warning_classes),
            "max_confidence": max([float(x.get("confidence", 0)) for x in flat_items], default=0),
        },
    }
```

## 11. 边界情况

| 场景 | 处理方式 |
|---|---|
| `detections` 为空 | 返回 `pass`，原因是未发现达到阈值的风险目标 |
| 某条结果缺少 `confidence` | 按 0 处理 |
| 某条结果缺少 `class_name` | 跳过该条 |
| 类别不在规则配置中 | 不触发审核风险 |
| 同一帧多个风险目标 | 都进入 `risk_triggers` |
| 多帧重复命中同类目标 | 保留最高置信度证据优先展示 |
| 没有证据图路径 | 不阻塞结论生成，但 `evidence_frames` 为空 |

## 12. 和人工复核的关系

机器自动审核只写入：

```json
{
  "machine_conclusion": "reject",
  "machine_conclusion_text": "不通过"
}
```

人工复核接口再写入：

```json
{
  "manual_conclusion": "pass",
  "reviewer": "张三",
  "note": "人工确认该目标不是风险物品"
}
```

最终页面展示时建议优先显示人工结论：

```text
如果 manual_conclusion 不为空
    -> 展示人工结论
否则
    -> 展示机器结论
```

## 13. 测试用例

| 编号 | 输入 | 规则 | 预期 |
|---|---|---|---|
| RULE-001 | 空检测结果 | 默认规则 | `pass` |
| RULE-002 | `knife 0.76` | reject=0.60 | `reject` |
| RULE-003 | `knife 0.45` | review=0.35, reject=0.60 | `review` |
| RULE-004 | `bottle 0.50` | warning_classes 包含 bottle | `review` |
| RULE-005 | `person 0.90` | person 不在规则中 | `pass` |
| RULE-006 | `knife 0.76` + `bottle 0.50` | 默认规则 | `reject` |
| RULE-007 | `knife 0.20` | review=0.35 | `pass` |

## 14. 验收标准

审核规则判断模块完成后，应满足：

```text
1. 能把 YOLO 检测结果转换成 pass/review/reject；
2. 能说明每个结论的触发原因；
3. 能记录触发审核的类别、置信度和帧时间；
4. 能返回证据帧路径给前端展示；
5. 空检测、低置信度、不在规则内类别不会误判为风险；
6. 多帧视频按最严重结果生成最终结论；
7. 结果能写入 analysis_report.json 并重新读取。
```

## 15. 违禁物品判定标准

本项目不做自定义训练，因此“违禁物品”必须定义为当前 YOLO 预训练模型能够识别的类别。使用 `yolo11n.pt` 时，模型主要基于 COCO 数据集类别，能稳定识别的相关类别包括：

| 类别 | 英文类别名 | 项目判定 |
|---|---|---|
| 刀具 | `knife` | 高风险，达到阈值直接不通过 |
| 剪刀 | `scissors` | 高风险，达到阈值直接不通过 |
| 棒球棒 | `baseball bat` | 高风险，可能作为攻击性器具，达到阈值直接不通过 |
| 酒瓶/瓶子 | `bottle` | 提醒类别，通常待复核 |
| 酒杯 | `wine glass` | 提醒类别，通常待复核 |
| 手机 | `cell phone` | 提醒类别，按项目场景可待复核 |

推荐规则配置：

```json
{
  "risk_classes": ["knife", "scissors", "baseball bat"],
  "warning_classes": ["bottle", "wine glass", "cell phone"],
  "reject_confidence": 0.60,
  "review_confidence": 0.35,
  "min_evidence_frames": 1
}
```

这里的“违禁物品”不是法律意义上的完整违禁品清单，而是本课堂项目中的“模型可识别风险物品”。例如枪支、毒品、血腥画面、裸露内容等，如果没有专门训练模型，不能只靠当前 `yolo11n.pt` 准确识别，报告中需要说明这些不属于本版本检测范围。

## 16. OpenCV 与 YOLO 的分工

### 16.1 OpenCV 负责什么

OpenCV 不负责判断物品类别，它主要负责素材处理和证据生成：

```text
图片：
    -> 读取图片
    -> 检查图片是否损坏
    -> 给 YOLO 提供图像数据
    -> 绘制检测框
    -> 保存证据图

视频：
    -> 打开视频
    -> 获取 FPS、总帧数、时长
    -> 按时间间隔采样关键帧
    -> 把采样帧送入 YOLO
    -> 保存命中风险的证据帧
```

也就是说，OpenCV 解决“从素材里取哪些画面出来分析”和“如何把证据保存下来”的问题。

### 16.2 YOLO 负责什么

YOLO 负责目标检测：

```text
输入：图片或视频采样帧
输出：目标类别、置信度、检测框坐标
```

示例输出：

```json
{
  "class_name": "knife",
  "confidence": 0.76,
  "bbox": [150, 90, 260, 360]
}
```

YOLO 只说明“画面中可能有一个 knife，置信度 0.76，位置在 bbox”。它本身不直接知道业务上是否应该通过、不通过或待复核。

### 16.3 审核规则负责什么

审核规则负责把 YOLO 检测结果转成业务结论：

```text
YOLO 识别到 knife 0.76
    -> class_name 属于 risk_classes
    -> confidence >= reject_confidence
    -> 自动结论：不通过
```

```text
YOLO 识别到 knife 0.42
    -> class_name 属于 risk_classes
    -> confidence 介于 0.35 和 0.60
    -> 自动结论：待复核
```

```text
YOLO 识别到 dog 0.90
    -> class_name 不在 risk_classes 和 warning_classes
    -> 自动结论：通过
```

## 17. 图片审核判定流程

图片只需要检测一次：

```text
读取图片
    -> YOLO 检测所有目标
    -> 遍历检测结果
    -> 判断是否命中 risk_classes 或 warning_classes
    -> 按最高风险结果给出结论
    -> 保存一张带框证据图
```

判定示例：

| YOLO 结果 | 规则判断 | 自动结论 |
|---|---|---|
| `knife 0.76` | 高风险类别，超过 0.60 | 不通过 |
| `scissors 0.48` | 高风险类别，超过 0.35 但低于 0.60 | 待复核 |
| `bottle 0.55` | 提醒类别，超过 0.35 | 待复核 |
| `person 0.92` | 不在规则类别内 | 通过 |
| 无检测结果 | 未命中风险规则 | 通过 |

## 18. 视频审核判定流程

视频不能每帧都检测，成本太高，因此使用 OpenCV 采样。

推荐策略：

```text
每 1 秒采样 1 帧
最多采样 120 帧
每帧送入 YOLO
所有帧按最严重结果汇总
```

视频最终结论：

```text
任意采样帧出现 knife/scissors/baseball bat 且置信度 >= 0.60
    -> 不通过

没有不通过，但任意采样帧出现风险或提醒类别且置信度 >= 0.35
    -> 待复核

所有采样帧都没有命中规则目标
    -> 通过
```

视频证据选择：

```text
优先保存触发不通过的帧
其次保存触发待复核的帧
同级别按置信度从高到低
最多保存 10 张证据帧
```

## 19. 为什么不能只用 OpenCV 判断违禁物品

OpenCV 可以做颜色、边缘、轮廓、运动变化等传统视觉处理，但它不知道一个物体是“刀”还是“剪刀”。例如：

```text
OpenCV 能发现一个银色长条形区域
但不能稳定判断它是刀、笔、勺子还是反光边缘
```

所以本项目采用：

```text
OpenCV：读取图片/视频、采样、保存证据
YOLO：识别物体类别和位置
规则系统：根据类别和置信度生成审核结论
```

这是最适合单日项目的实现方式，既能跑通，又能解释清楚。

## 20. 推荐课堂表述

答辩时可以这样说明：

```text
我们没有把所有现实违禁品都作为检测范围，而是根据当前 YOLO 预训练模型能识别的 COCO 类别，选取 knife、scissors、baseball bat 作为高风险类别，选取 bottle、wine glass、cell phone 作为提醒类别。

OpenCV 负责读取图片和视频，对视频按 1 秒间隔采样，并保存带检测框的证据帧。YOLO 负责识别每张图或采样帧中的目标类别、置信度和位置。最后规则引擎根据类别和置信度阈值输出通过、待复核或不通过。
```

## 21. 类别是否只能有三类

不是只能有三类。当前选择 `knife`、`scissors`、`baseball bat` 是因为它们属于 YOLO COCO 预训练模型已经支持的类别，课堂项目可以直接使用，不需要重新训练。

类别扩展分为两种情况：

### 21.1 使用预训练模型已有类别

如果类别已经在当前 YOLO 模型类别表中，可以直接加入规则配置，不需要训练。

例如：

```json
{
  "risk_classes": ["knife", "scissors", "baseball bat"],
  "warning_classes": ["bottle", "wine glass", "cell phone", "person"]
}
```

这种方式最快，但只能识别预训练模型本来就会识别的目标。

### 21.2 训练自定义违禁类别

如果要识别当前模型不支持的类别，例如：

```text
gun
cigarette
vape
drug
blood
explicit_content
custom_game_weapon
```

就需要自己准备数据集并微调 YOLO。

注意：YOLO 是目标检测模型，适合检测“有明确位置框的物体”，例如枪、烟、刀、酒瓶、游戏武器。不适合单独判断抽象内容，例如“低俗”“暴力倾向”“违规文案”。这类内容通常需要分类模型、OCR 或多模态模型配合。

## 22. 自定义 YOLO 训练流程

### 22.1 第一步：确定类别

先定义本项目要检测的类别，例如：

```text
0 knife
1 gun
2 cigarette
3 wine_bottle
4 custom_weapon
```

类别不要太多。课堂项目建议 3 到 5 类，方便标注和训练。

### 22.2 第二步：准备图片数据

每个类别至少准备：

```text
最低可演示：每类 50-100 张
较稳定效果：每类 300-1000 张
```

图片来源可以包括：

```text
真实素材截图
公开视频截图
游戏录屏截图
自己拍摄或收集的测试图片
```

数据要包含不同场景：

```text
不同角度
不同光照
不同大小
遮挡情况
复杂背景
正样本和负样本
```

负样本也重要，例如没有违禁物品的普通画面，避免模型误报。

### 22.3 第三步：标注数据

使用标注工具给目标画框：

```text
LabelImg
Roboflow
CVAT
Label Studio
```

YOLO 标注格式为每张图片对应一个 `.txt`：

```text
class_id x_center y_center width height
```

坐标都是 0 到 1 之间的归一化数值。

示例：

```text
1 0.5123 0.4388 0.2450 0.3100
```

含义：

```text
类别 1
目标中心点 x = 0.5123
目标中心点 y = 0.4388
目标宽度 = 0.2450
目标高度 = 0.3100
```

### 22.4 第四步：整理数据集目录

推荐目录：

```text
dataset/
├─ images/
│  ├─ train/
│  ├─ val/
│  └─ test/
├─ labels/
│  ├─ train/
│  ├─ val/
│  └─ test/
└─ data.yaml
```

训练集、验证集、测试集比例：

```text
train 70%
val   20%
test  10%
```

### 22.5 第五步：编写 data.yaml

示例：

```yaml
path: D:/PythonProject/Day08-/dataset
train: images/train
val: images/val
test: images/test

names:
  0: knife
  1: gun
  2: cigarette
  3: wine_bottle
  4: custom_weapon
```

### 22.6 第六步：开始训练

在已有环境中执行：

```powershell
conda activate yolo
yolo detect train model=models/yolo11n.pt data=dataset/data.yaml epochs=50 imgsz=640 batch=8
```

如果显存不足：

```powershell
yolo detect train model=models/yolo11n.pt data=dataset/data.yaml epochs=50 imgsz=640 batch=4
```

如果只是课堂演示，可以先训练少一点：

```powershell
yolo detect train model=models/yolo11n.pt data=dataset/data.yaml epochs=20 imgsz=640 batch=4
```

训练完成后，权重通常在：

```text
runs/detect/train/weights/best.pt
```

### 22.7 第七步：验证模型

```powershell
yolo detect val model=runs/detect/train/weights/best.pt data=dataset/data.yaml
```

重点看：

```text
Precision：预测为违禁时有多少是真的
Recall：真实违禁目标有多少被找出来
mAP50：检测框和类别综合效果
```

内容审核项目里，建议更重视召回率：

```text
Recall 低 -> 漏检多，风险大
Precision 低 -> 误报多，人工复核压力大
```

### 22.8 第八步：替换项目模型

将训练好的模型复制到：

```text
models/custom_review.pt
```

然后修改 Flask 初始化：

```python
cv = CVEngine(model_path=BASE_DIR / "models" / "custom_review.pt")
```

同时更新规则：

```json
{
  "risk_classes": ["gun", "knife", "cigarette", "custom_weapon"],
  "warning_classes": ["wine_bottle"],
  "reject_confidence": 0.55,
  "review_confidence": 0.30
}
```

自训练模型刚开始不稳定，阈值可以略低一些，再用测试集调整。

## 23. 课堂项目建议

本日项目时间只有 1 天，不建议现场从零训练模型。推荐方案：

```text
正式实现：
    使用 yolo11n.pt 已有类别完成闭环

文档说明：
    写清楚后续可以通过自定义数据集训练 gun、cigarette、vape 等类别

演示加分：
    如果已有标注数据，可以用少量数据微调一个 custom_review.pt
```

最稳妥的答辩说法：

```text
当前版本为了保证单日项目可运行，先使用 YOLO 预训练模型中已有的 knife、scissors、baseball bat 作为高风险类别。系统规则是配置化的，后续如果要扩展 gun、cigarette、vape 等类别，需要采集和标注数据，以 YOLO 格式训练自定义模型，再把 best.pt 替换到 models 目录，并更新 risk_classes 即可。
```
