# API 接口文档

<!-- TODO: 后端工程师填写 -->

## 公共接口

| 方法 | 路径 | 说明 | 进度 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 | ✅ 已实现 |
| POST | `/api/jobs` | 创建任务 | 待实现 |
| GET | `/api/jobs` | 任务列表 | 待实现 |
| GET | `/api/jobs/<id>` | 任务详情 | 待实现 |
| DELETE | `/api/jobs/<id>` | 删除任务 | 待实现 |

## 方向 A 接口

| 方法 | 路径 | 说明 | 进度 |
|------|------|------|------|
| POST | `/api/jobs/<id>/analyze` | 触发分析 | 待实现 |
| PATCH | `/api/jobs/<id>/review` | 人工复核 | 待实现 |
| GET | `/api/jobs/<id>/report` | 审核报告 | 待实现 |

## 响应格式

### 成功

```json
{ "ok": true, "data": {...} }
```

### 失败

```json
{ "ok": false, "error": "描述信息" }
```
