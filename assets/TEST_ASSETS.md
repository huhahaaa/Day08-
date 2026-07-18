# 测试图片说明

图片来源：

- `onullusoy/harmful-contents`
- Hugging Face: https://huggingface.co/datasets/onullusoy/harmful-contents
- 该数据集 README 标注为 research-and-non-commercial-use，课堂项目测试使用时建议仅作本地演示和报告说明。

`zigg-ai/content-regions-distrib-yolo-23k` 不作为本项目 YOLO 物品审核测试图来源，因为它的类别是内容区域分类，例如 `digital_videogame`、`footage_scene`，不是刀具、瓶子、人物等 COCO 物体类别。

## 已选测试图

| 文件 | 来源路径 | YOLO 主要检测结果 | 自动审核结论 | 用途 |
|---|---|---|---|---|
| `review_reject_scissors.jpg` | `data/test/871.jpg` | `scissors 0.7421` | 不通过 | 测试高风险类别超过 0.60 |
| `review_risk_knife_review.jpg` | `data/train/58.jpg` | `knife 0.4829`、`person 0.8567` | 待复核 | 测试高风险类别低置信度 |
| `review_warning_bottle_person.jpg` | `data/train/136.jpg` | `bottle 0.8095`、`person 0.7928` | 待复核 | 测试提醒类别和人物 |
| `review_warning_bottle_wineglass.jpg` | `data/train/180.jpg` | `wine glass 0.9124`、`bottle 0.8976` | 待复核 | 测试酒瓶/酒杯提醒类别 |
| `review_person_only.jpg` | `data/train/2843.jpg` | `person 0.8599` | 通过 | 测试非规则类别不误判 |

## 当前规则

来自项目根目录 `default_rules.json`：

```json
{
  "risk_classes": ["knife", "scissors", "baseball bat"],
  "warning_classes": ["bottle", "wine glass", "cell phone"],
  "reject_confidence": 0.60,
  "review_confidence": 0.35
}
```

## 使用方式

启动项目后，在前端上传以上图片即可测试：

```text
assets/review_reject_scissors.jpg
assets/review_risk_knife_review.jpg
assets/review_warning_bottle_person.jpg
assets/review_warning_bottle_wineglass.jpg
assets/review_person_only.jpg
```

