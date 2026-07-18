# 测试报告

## 测试环境

| 项目 | 版本 |
|------|------|
| 操作系统 | Windows 11 |
| Python | 3.11 |
| Flask | 3.0.0 |
| YOLO | 11n (ultralytics) |
| 浏览器 | Chrome |

## 测试概述

本项目为 **方向 A：智能数字媒体内容审核系统**，测试覆盖正常流程、异常流程和接口功能三个维度。

## 界面截图

### 工作台首页

![工作台首页](file:///D:/Gongchengshixun/Day08-/screenshots/screenshot_home.png)

### 任务列表与详情

![任务列表](file:///D:/Gongchengshixun/Day08-/screenshots/screenshot_task_list.png)

### 任务详情页（包含检测结果和证据帧）

![任务详情](file:///D:/Gongchengshixun/Day08-/screenshots/screenshot_task_detail.png)

## 用例执行结果

### 正常测试（5条）

| 用例编号 | 描述 | 预期结果 | 实际结果 | 状态 |
|---------|------|---------|---------|------|
| TC-01 | 上传合法视频 | 返回 job_id，状态最终 completed | 返回 job_id，状态 completed，检测到 142 个目标 | ✅ PASS |
| TC-02 | 上传合法图片 | 返回 job_id，状态最终 completed | 返回 job_id，状态 completed | ✅ PASS |
| TC-03 | 查询任务列表 | 返回所有任务列表 | 返回完整任务列表，包含所有状态 | ✅ PASS |
| TC-04 | 查询任务详情 | 返回任务完整信息 | 返回任务详情、检测结果、证据帧 | ✅ PASS |
| TC-05 | 人工复核 | 更新 verdict 为 pass/review/reject | verdict 更新成功，记录保存 | ✅ PASS |

### 异常测试（5条）

| 用例编号 | 描述 | 预期结果 | 实际结果 | 状态 |
|---------|------|---------|---------|------|
| TC-06 | 上传空文件 | 任务失败，error 有提示 | 状态 failed，error="格式不支持: .txt" | ✅ PASS |
| TC-07 | 上传伪装视频（文本内容） | 任务失败，error 有提示 | 状态 failed，error="视频读取失败或格式不支持" | ✅ PASS |
| TC-08 | 上传损坏视频 | 任务失败，error 有提示 | 状态 failed，error="视频读取失败或格式不支持" | ✅ PASS |
| TC-09 | 删除运行中任务 | 返回 409 Conflict | 返回 409，提示"无法删除运行中的任务" | ✅ PASS |
| TC-10 | 删除不存在任务 | 返回 404 Not Found | 返回 404，提示"任务不存在" | ✅ PASS |

## API 测试记录

### 1. 健康检查

```powershell
curl.exe http://127.0.0.1:7880/api/health
```

**响应：**
```json
{
  "status": "ok",
  "model_ready": true,
  "model_name": "yolo11n.pt + custom_gun.pt",
  "model_names": ["yolo11n.pt", "custom_gun.pt"]
}
```

### 2. 创建任务

```powershell
curl.exe -X POST http://127.0.0.1:7880/api/jobs -F "file=@testvideo/test.mp4" -F "project_name=测试任务"
```

**响应：**
```json
{"ok": true, "job_id": "20260718_202145_cdcf0d9e", "status": "queued"}
```

### 3. 查询任务列表

```powershell
curl.exe http://127.0.0.1:7880/api/jobs
```

**响应：** 返回所有任务列表（省略详细数据）

### 4. 查询单个任务

```powershell
curl.exe http://127.0.0.1:7880/api/jobs/20260718_202145_cdcf0d9e
```

**响应：** 返回任务完整信息，包含检测结果、证据帧等

### 5. 触发分析

```powershell
curl.exe -X POST http://127.0.0.1:7880/api/jobs/20260718_202145_cdcf0d9e/analyze
```

**响应：**
```json
{"ok": true, "job_id": "20260718_202145_cdcf0d9e", "status": "running"}
```

### 6. 人工复核

```powershell
$body = @{ verdict = "pass"; note = "确认通过"; reviewer = "测试员" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:7880/api/jobs/20260718_202145_cdcf0d9e/review" -Method PATCH -ContentType "application/json" -Body $body
```

**响应：**
```json
{"ok": true, "job_id": "20260718_202145_cdcf0d9e", "verdict": "pass"}
```

### 7. 删除已完成任务

```powershell
curl.exe -X DELETE http://127.0.0.1:7880/api/jobs/20260718_202145_cdcf0d9e
```

**响应：**
```json
{"ok": true}
```

### 8. 删除运行中任务

```powershell
curl.exe -X DELETE -i http://127.0.0.1:7880/api/jobs/20260718_203805_71c11934
```

**响应：**
```text
HTTP/1.1 409 CONFLICT
{"ok": false, "error": "无法删除运行中的任务"}
```

## 错误处理记录

### 空文件处理

```powershell
curl.exe -X POST http://127.0.0.1:7880/api/jobs -F "file=@empty.txt" -F "project_name=异常测试-空文件"
```

**结果：**
- 任务创建成功：`job_id=20260718_202319_00181d10`
- 分析后状态：`failed`
- 错误信息：`"格式不支持: .txt"`

### 伪装视频处理

```powershell
curl.exe -X POST http://127.0.0.1:7880/api/jobs -F "file=@fake.mp4" -F "project_name=异常测试-伪装视频"
```

**结果：**
- 任务创建成功：`job_id=20260718_202403_264b558c`
- 分析后状态：`failed`
- 错误信息：`"视频读取失败或格式不支持"`

### 损坏视频处理

```powershell
curl.exe -X POST http://127.0.0.1:7880/api/jobs -F "file=@corrupt.mp4" -F "project_name=异常测试-损坏视频"
```

**结果：**
- 任务创建成功：`job_id=20260718_202449_4af2cc0c`
- 分析后状态：`failed`
- 错误信息：`"视频读取失败或格式不支持"`

## 测试总结

### 功能完整性

| 功能 | 状态 | 说明 |
|------|------|------|
| 素材上传 | ✅ | 支持图片和视频 |
| 任务创建 | ✅ | 返回 job_id，异步处理 |
| 模型推理 | ✅ | YOLO 检测正常 |
| 审核规则 | ✅ | 通过/待复核/不通过 |
| 证据帧保存 | ✅ | 自动保存检测证据 |
| 人工复核 | ✅ | 支持修改结论 |
| 报告下载 | ✅ | JSON 报告和证据 ZIP |
| 任务删除 | ✅ | 支持 completed/failed |

### 异常处理能力

| 场景 | 状态 | 说明 |
|------|------|------|
| 空文件 | ✅ | 明确错误提示 |
| 伪装视频 | ✅ | 明确错误提示 |
| 损坏视频 | ✅ | 明确错误提示 |
| 运行中删除 | ✅ | 返回 409 Conflict |
| 不存在任务 | ✅ | 返回 404 Not Found |
| 服务稳定性 | ✅ | 异常测试后服务不崩溃 |

### 测试覆盖度

- **正常测试：** 5/5 ✅
- **异常测试：** 5/5 ✅
- **API 测试：** 8/8 ✅
- **总覆盖率：** 18/18 ✅