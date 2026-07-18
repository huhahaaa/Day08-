# Bug 记录

## Bug 统计

| 类型 | 数量 |
|------|------|
| 严重 Bug | 0 |
| 可用性 Bug | 3 |
| 已修复 | 3 |

## Bug 详情

| 编号 | 问题现象 | 复现步骤 | 原因 | 修复方案 | 验证结果 |
|------|----------|----------|------|----------|----------|
| BUG-001 | 上传空文件/伪装视频/损坏视频后，前端任务详情页没有显示错误信息，只显示"状态未知" | 1. 上传 empty.txt<br>2. 点击"查看"按钮<br>3. 任务详情页只显示状态为 failed，但看不到具体错误原因 | [app.js](file:///D:/Gongchengshixun/Day08-/static/js/app.js) 第94-153行 viewJobDetail 函数未处理 `j.error` 字段，当任务失败时没有展示错误信息区域 | 在 viewJobDetail 函数中增加错误信息展示逻辑：当 `j.status === 'failed' && j.error` 时，渲染红色错误提示框显示具体错误原因 | ✅ 已验证：失败任务详情页现在正确显示红色错误信息框，包含完整的错误描述 |
| BUG-002 | 删除运行中任务时，API 返回 HTTP 400 Bad Request 而非标准的 409 Conflict；删除不存在任务时返回 400 而非 404 Not Found | 1. 创建任务并启动分析<br>2. 在 running 状态时执行 DELETE 请求<br>3. 观察返回的 HTTP 状态码 | [app.py](file:///D:/Gongchengshixun/Day08-/app.py) 第94-100行 api_delete_job 函数将所有失败情况统一返回 400，没有区分"任务不存在"和"状态不允许删除"两种场景 | 重构 api_delete_job 函数：<br>1. 任务不存在 → 返回 HTTP 404<br>2. 任务存在但状态不允许删除 → 返回 HTTP 409<br>3. 删除成功 → 返回 HTTP 200 | ✅ 已验证：删除运行中任务返回 409 Conflict，删除不存在任务返回 404 Not Found |
| BUG-003 | 任务列表中失败任务的结论显示为"待审核"而非"失败"状态 | 1. 上传损坏视频<br>2. 查看任务列表<br>3. 失败任务的"结论"列显示为"待审核" | [app.js](file:///D:/Gongchengshixun/Day08-/static/js/app.js) 第65行仅根据 `verdict` 字段判断结论，未考虑 `status === 'failed'` 的情况，导致失败任务显示默认值"待审核" | 在任务列表渲染逻辑中增加判断：当 `j.status === 'failed'` 时，结论显示为"失败"，标签样式为红色 `tag-failed` | ✅ 已验证：失败任务在列表中显示红色"失败"标签，与其他状态区分明显 |

## Bug 详细分析

### BUG-001：前端未显示错误信息

**问题描述：**
当任务因异常输入（空文件、伪装视频、损坏视频）而失败时，前端任务详情页面只显示状态为 `failed`，但没有展示具体的错误原因。用户无法知道任务失败的具体原因，影响问题排查和用户体验。

**复现步骤：**
1. 创建空文件：`echo $null > empty.txt`
2. 通过前端上传 empty.txt
3. 触发分析：点击"启动审核"按钮
4. 等待任务状态变为 failed
5. 点击"查看"按钮查看任务详情
6. 观察页面：只显示状态为 failed，没有错误信息

**根本原因：**
[app.js](file:///D:/Gongchengshixun/Day08-/static/js/app.js) 中的 `viewJobDetail` 函数没有处理 `error` 字段。当任务失败时，后端正确返回了 `error` 字段，但前端没有读取和展示该字段。

**修复方案：**
在 `viewJobDetail` 函数的 HTML 生成逻辑中，增加以下代码：

```javascript
if (j.status === 'failed' && j.error) {
    html += '<div class="error-box"><strong>错误信息</strong><br>' + j.error + '</div>';
}
```

同时在 [app.css](file:///D:/Gongchengshixun/Day08-/static/css/app.css) 中添加错误框样式：

```css
.error-box {
    background: #fff5f5;
    border: 1px solid #ffebee;
    border-radius: 4px;
    padding: 12px;
    margin: 10px 0;
    color: #dc3545;
}
```

**验证方法：**
1. 上传 empty.txt 并触发分析
2. 查看任务详情，确认错误框显示"格式不支持: .txt"
3. 上传 fake.mp4 并触发分析
4. 查看任务详情，确认错误框显示"视频读取失败或格式不支持"

---

### BUG-002：删除接口返回码不符合 REST 规范

**问题描述：**
根据 RESTful API 设计规范，资源状态冲突应返回 HTTP 409 Conflict，资源不存在应返回 HTTP 404 Not Found。但原代码将所有删除失败情况统一返回 HTTP 400 Bad Request，不符合标准。

**复现步骤：**
1. 创建任务并启动分析
2. 在任务处于 running 状态时，执行 DELETE 请求
3. 使用 `-i` 参数观察 HTTP 状态码，发现返回 400 而非 409

**根本原因：**
[app.py](file:///D:/Gongchengshixun/Day08-/app.py) 中的 `api_delete_job` 函数直接调用 `jobs.delete_job()`，该方法返回布尔值，无法区分"任务不存在"和"状态不允许删除"两种失败原因。

**修复方案：**
重构 `api_delete_job` 函数，先查询任务状态，再根据不同情况返回不同的 HTTP 状态码：

```python
@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_delete_job(job_id):
    """删除任务（仅 completed/failed 可删）"""
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "任务不存在"}), 404
    status = job.get("status")
    if status not in ["completed", "failed"]:
        return jsonify({"ok": False, "error": "无法删除运行中的任务"}), 409
    jobs.delete_job(job_id)
    return jsonify({"ok": True})
```

**验证方法：**
1. 删除运行中任务：`curl.exe -X DELETE -i http://127.0.0.1:7880/api/jobs/<running_job_id>`
   - 预期：返回 HTTP 409 Conflict
   - 实际：返回 HTTP 409 Conflict ✅

2. 删除不存在任务：`curl.exe -X DELETE -i http://127.0.0.1:7880/api/jobs/nonexistent_id`
   - 预期：返回 HTTP 404 Not Found
   - 实际：返回 HTTP 404 Not Found ✅

3. 删除已完成任务：`curl.exe -X DELETE http://127.0.0.1:7880/api/jobs/<completed_job_id>`
   - 预期：返回 HTTP 200 OK
   - 实际：返回 HTTP 200 OK ✅

---

### BUG-003：任务列表失败任务显示不正确

**问题描述：**
失败的任务在任务列表中"结论"列显示为"待审核"，应显示"失败"状态，以便用户快速识别异常任务。

**复现步骤：**
1. 上传损坏视频 corrupt.mp4
2. 触发分析，等待任务失败
3. 查看任务列表，观察失败任务的结论列

**根本原因：**
[app.js](file:///D:/Gongchengshixun/Day08-/static/js/app.js) 第65行的列表渲染逻辑仅根据 `verdict` 字段判断结论，失败任务的 `verdict` 为 null，所以显示默认值"待审核"。

**修复方案：**
在任务列表渲染逻辑中增加 `status === 'failed'` 的判断：

```javascript
var v = j.status === 'failed' ? '失败' : (j.verdict || '待审核');
var tagClass = j.status === 'failed' ? 'tag-failed' : (v === 'pass' ? 'tag-pass' : (v === 'review' ? 'tag-review' : (v === 'reject' ? 'tag-reject' : 'tag-created')));
```

同时在 [app.css](file:///D:/Gongchengshixun/Day08-/static/css/app.css) 中添加失败标签样式：

```css
.tag-failed { background: #f8d7da; color: #dc3545; }
```

**验证方法：**
1. 查看任务列表
2. 确认失败任务的结论列显示红色"失败"标签
3. 确认其他状态任务显示正确的标签样式

## Bug 修复影响范围

| Bug | 修复文件 | 影响范围 |
|-----|----------|----------|
| BUG-001 | app.js、app.css | 前端任务详情页 |
| BUG-002 | app.py | 删除接口 API |
| BUG-003 | app.js、app.css | 前端任务列表 |

## 修复总结

所有发现的 Bug 均已修复并验证通过，系统现在能够：
1. ✅ 正确显示失败任务的错误信息
2. ✅ 遵循 RESTful API 返回码规范
3. ✅ 在任务列表中正确展示失败状态