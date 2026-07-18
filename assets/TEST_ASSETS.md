# 测试图片说明

本目录保留的是课堂演示用测试图片，目标是覆盖方向 A 的三种审核结论：

```text
通过
待复核
不通过
```

## 来源说明

正式样本来自两类来源：

1. Openverse 检索到的 CC/公开图片，优先用于清晰物体演示；
2. Hugging Face 数据集 `onullusoy/harmful-contents`，用于补充人物、瓶子、低置信度刀具等场景。

`zigg-ai/content-regions-distrib-yolo-23k` 不作为本项目 YOLO 物品审核测试图来源，因为它的类别是内容区域分类，例如 `digital_videogame`、`footage_scene`，不是刀具、瓶子、人物等 COCO 物体类别。

## 推荐演示图片

| 文件 | 来源 | YOLO 主要检测结果 | 自动审核结论 | 用途 |
|---|---|---|---|---|
| `review_reject_scissors.jpg` | Openverse / Flickr, `Scissors`, James Bowe, CC BY | `scissors 0.9274` | 不通过 | 清晰剪刀，高风险类别超过 0.60 |
| `review_reject_knife_clear.jpg` | Openverse / Flickr, `Kitchen Knife I`, DaveCrosby, CC BY-SA | `knife 0.8479` | 不通过 | 清晰刀具，高风险类别超过 0.60 |
| `review_reject_baseball_bat.jpg` | Openverse / Flickr, `Man on a beach holds a baseball bat`, simpleinsomnia, CC BY | `baseball bat 0.8685`、`person 0.8676` | 不通过 | 棒球棒，高风险类别超过 0.60 |
| `review_warning_wine_bottle_clear.jpg` | Openverse / Rawpixel, `Free wine glasses, bottles image`, CC0 | `wine glass 0.8790`、`bottle 0.6538` | 待复核 | 酒杯/酒瓶提醒类别 |
| `review_person_only.jpg` | `onullusoy/harmful-contents`, `data/train/2843.jpg` | `person 0.8599` | 通过 | 人物不在风险规则中，不误判 |

## 备用测试图片

| 文件 | 来源 | YOLO 主要检测结果 | 自动审核结论 | 用途 |
|---|---|---|---|---|
| `review_risk_knife_review.jpg` | `onullusoy/harmful-contents`, `data/train/58.jpg` | `knife 0.4829`、`person 0.8567` | 待复核 | 高风险类别低置信度，测试复核阈值 |
| `review_warning_bottle_person.jpg` | `onullusoy/harmful-contents`, `data/train/136.jpg` | `bottle 0.8095`、`person 0.7928` | 待复核 | 瓶子 + 人物 |
| `review_warning_bottle_wineglass.jpg` | `onullusoy/harmful-contents`, `data/train/180.jpg` | `wine glass 0.9124`、`bottle 0.8976` | 待复核 | 酒杯/酒瓶提醒类别 |

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

启动项目后，在前端上传以下推荐图片即可覆盖三种结论：

```text
assets/review_reject_scissors.jpg
assets/review_reject_knife_clear.jpg
assets/review_reject_baseball_bat.jpg
assets/review_warning_wine_bottle_clear.jpg
assets/review_person_only.jpg
```

如果需要测试“高风险类别低置信度待复核”，使用：

```text
assets/review_risk_knife_review.jpg
```

