// ===================== 全局变量 =====================
var currentJobId = null;
var pollTimer = null;

// ===================== 工具函数 =====================
function showMessage(elId, msg, type) {
    var el = document.getElementById(elId);
    if (!el) return;
    el.textContent = msg;
    el.className = 'result-area';
    if (type === 'success') el.classList.add('success');
    else if (type === 'error') el.classList.add('error');
    else if (type === 'loading') el.classList.add('loading');
}

function getJobId() { return currentJobId; }

// ===================== 1. 上传 =====================
document.getElementById('uploadBtn').onclick = function() {
    var file = document.getElementById('fileInput').files[0];
    if (!file) {
        showMessage('uploadResult', '⚠️ 请先选择文件', 'error');
        return;
    }

    var formData = new FormData();
    formData.append('file', file);
    var name = document.getElementById('projectNameInput').value.trim();
    if (name) formData.append('project_name', name);

    showMessage('uploadResult', '⏳ 上传中...', 'loading');
    this.disabled = true;

    fetch('/api/jobs', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.job_id) {
            showMessage('uploadResult', '✅ 上传成功！任务ID：' + data.job_id, 'success');
            loadJobList();
            viewJobDetail(data.job_id);
        } else {
            showMessage('uploadResult', '❌ ' + (data.error || '上传失败'), 'error');
        }
    })
    .catch(function(e) {
        showMessage('uploadResult', '❌ 请求失败：' + e, 'error');
    })
    .finally(function() {
        document.getElementById('uploadBtn').disabled = false;
    });
};

// ===================== 2. 任务列表 =====================
function loadJobList() {
    fetch('/api/jobs')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        var el = document.getElementById('jobList');
        if (!data || !data.length) {
            el.innerHTML = '<p style="color:#999;">暂无任务</p>';
            return;
        }
        var html = '<table><thead><tr><th>任务ID</th><th>文件名</th><th>状态</th><th>结论</th><th></th></tr></thead><tbody>';
        data.forEach(function(j) {
            var v = j.status === 'failed' ? '失败' : (j.verdict || '待审核');
            var tagClass = j.status === 'failed' ? 'tag-failed' : (v === 'pass' ? 'tag-pass' : (v === 'review' ? 'tag-review' : (v === 'reject' ? 'tag-reject' : 'tag-created')));
            html += '<tr>' +
                '<td class="job-id">' + j.job_id + '</td>' +
                '<td>' + (j.asset_name || '-') + '</td>' +
                '<td>' + (j.status || 'created') + '</td>' +
                '<td><span class="tag ' + tagClass + '">' + v + '</span></td>' +
                '<td><button onclick="viewJobDetail(\'' + j.job_id + '\')">查看</button></td>' +
                '</tr>';
        });
        html += '</tbody></table>';
        el.innerHTML = html;
    })
    .catch(function() {
        document.getElementById('jobList').innerHTML = '<p style="color:#dc3545;">加载失败</p>';
    });
}
document.getElementById('refreshBtn').onclick = loadJobList;

// ===================== 3. 任务详情 =====================
function viewJobDetail(jobId) {
    currentJobId = jobId;
    document.getElementById('detailCard').classList.remove('hidden');
    document.getElementById('reviewCard').classList.add('hidden');
    showMessage('detailResult', '⏳ 加载中...', 'loading');

    fetch('/api/jobs/' + jobId)
    .then(function(r) { return r.json(); })
    .then(function(j) {
        var content = document.getElementById('detailContent');
        var v = j.status === 'failed' ? '失败' : (j.verdict || '待审核');
        var tagClass = j.status === 'failed' ? 'tag-failed' : (v === 'pass' ? 'tag-pass' : (v === 'review' ? 'tag-review' : (v === 'reject' ? 'tag-reject' : 'tag-created')));

        var html = '<div class="detail-grid">';
        html += '<div><strong>任务ID</strong><br>' + j.job_id + '</div>';
        html += '<div><strong>文件名</strong><br>' + (j.asset_name || '-') + '</div>';
        html += '<div><strong>状态</strong><br>' + (j.status || 'created') + '</div>';
        html += '<div><strong>结论</strong><br><span class="tag ' + tagClass + '">' + v + '</span></div>';
        html += '<div><strong>创建时间</strong><br>' + (j.created_at || '-') + '</div>';
        html += '<div><strong>完成时间</strong><br>' + (j.completed_at || '-') + '</div>';
        html += '</div>';

        if (j.status === 'failed' && j.error) {
            html += '<div class="error-box"><strong>错误信息</strong><br>' + j.error + '</div>';
        }

        // 显示原始素材预览
        if (j.asset_name) {
            var ext = j.asset_name.split('.').pop().toLowerCase();
            var inputUrl = '/api/jobs/' + jobId + '/input/' + encodeURIComponent(j.asset_name);
            html += '<h4>原始素材</h4>';
            if (['jpg','jpeg','png','bmp','webp'].indexOf(ext) !== -1) {
                html += '<img src="' + inputUrl + '" onerror="this.style.display=\'none\'">';
            } else if (['mp4','avi','mov','mkv'].indexOf(ext) !== -1) {
                html += '<video controls width="300" src="' + inputUrl + '"></video>';
            } else {
                html += '<p>' + j.asset_name + '</p>';
            }
        }

        if (j.result) {
            var r = j.result;
            var summary = r.summary || {};
            var review = r.review || {};
            html += '<h4>检测结果</h4><div class="detail-grid">';
            html += '<div><strong>检测目标数</strong><br>' + (summary.total_detections || 0) + '</div>';
            html += '<div><strong>机器结论</strong><br>' + (review.machine_conclusion_text || review.machine_conclusion || '-') + '</div>';
            html += '<div><strong>原因</strong><br>' + (review.reason || '-') + '</div>';
            html += '</div>';

            // 显示证据图片（evidence_frames 是相对路径如 "evidence/frame_000000.jpg"）
            var evidenceFrames = r.evidence_frames || [];
            if (evidenceFrames.length > 0) {
                html += '<h4>证据帧</h4><div class="evidence-thumbs">';
                evidenceFrames.forEach(function(fpath) {
                    // 取文件名（去掉 "evidence/" 前缀）
                    var fname = fpath.replace(/\\/g, '/').split('/').pop();
                    var url = '/api/jobs/' + jobId + '/evidence/' + encodeURIComponent(fname);
                    html += '<img src="' + url + '" onerror="this.style.display=\'none\'" title="' + fname + '">';
                });
                html += '</div>';
            }
        }

        if (j.review) {
            html += '<h4>人工复核</h4><div class="detail-grid">';
            html += '<div><strong>原结论</strong><br>' + (j.review.original_verdict || '-') + '</div>';
            html += '<div><strong>新结论</strong><br>' + (j.review.new_verdict || '-') + '</div>';
            html += '<div><strong>备注</strong><br>' + (j.review.note || '-') + '</div>';
            html += '</div>';
        }

        content.innerHTML = html;
        showMessage('detailResult', '✅ 加载完成', 'success');

        // 控制审核按钮：仅 queued 状态可启动
        var analyzeBtn = document.getElementById('analyzeBtn');
        if (j.status === 'running' || j.status === 'completed') {
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = j.status === 'completed' ? '✅ 已审核' : '⏳ 审核中';
        } else {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = '▶ 启动审核';
        }

        // 复核面板：仅 completed 显示
        if (j.status === 'completed') {
            document.getElementById('reviewCard').classList.remove('hidden');
        } else {
            document.getElementById('reviewCard').classList.add('hidden');
        }

        // 删除按钮：仅 completed/failed 可删
        var delBtn = document.getElementById('deleteJobBtn');
        if (j.status === 'completed' || j.status === 'failed') {
            delBtn.style.display = '';
        } else {
            delBtn.style.display = 'none';
        }

        if (j.status === 'queued' || j.status === 'running') {
            startPolling(jobId);
        } else {
            stopPolling();
        }
    })
    .catch(function(e) {
        showMessage('detailResult', '❌ 加载失败：' + e, 'error');
    });
}

// ===================== 4. 启动审核 =====================
document.getElementById('analyzeBtn').onclick = function() {
    var id = getJobId();
    if (!id) return;
    showMessage('detailResult', '⏳ 正在启动...', 'loading');
    this.disabled = true;

    fetch('/api/jobs/' + id + '/analyze', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.ok) {
            showMessage('detailResult', '⏳ 审核已启动，等待完成...', 'loading');
            startPolling(id);
        } else {
            showMessage('detailResult', '❌ ' + (data.error || '启动失败'), 'error');
        }
    })
    .catch(function(e) {
        showMessage('detailResult', '❌ ' + e, 'error');
    })
    .finally(function() {
        document.getElementById('analyzeBtn').disabled = false;
    });
};

// ===================== 5. 人工复核 =====================
function doReview(verdict) {
    var id = getJobId();
    if (!id) return;
    var note = document.getElementById('reviewNote').value || '';
    fetch('/api/jobs/' + id + '/review', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verdict: verdict, note: note })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.ok) {
            document.getElementById('reviewResult').textContent = '✅ 复核成功！结论：' + verdict;
            document.getElementById('reviewResult').className = 'result-area success';
            viewJobDetail(id);
            loadJobList();
        } else {
            document.getElementById('reviewResult').textContent = '❌ ' + (data.error || '复核失败');
            document.getElementById('reviewResult').className = 'result-area error';
        }
    })
    .catch(function(e) {
        document.getElementById('reviewResult').textContent = '❌ ' + e;
        document.getElementById('reviewResult').className = 'result-area error';
    });
}
document.getElementById('reviewPassBtn').onclick = function() { doReview('pass'); };
document.getElementById('reviewReviewBtn').onclick = function() { doReview('review'); };
document.getElementById('reviewRejectBtn').onclick = function() { doReview('reject'); };

// ===================== 6. 下载 =====================
document.getElementById('downloadReportBtn').onclick = function() {
    var id = getJobId();
    if (id) window.open('/api/jobs/' + id + '/report?download=1', '_blank');
};
document.getElementById('downloadEvidenceBtn').onclick = function() {
    var id = getJobId();
    if (id) window.open('/api/jobs/' + id + '/evidence', '_blank');
};

// ===================== 7. 删除 =====================
document.getElementById('deleteJobBtn').onclick = function() {
    var id = getJobId();
    if (!id) return;
    if (!confirm('确认删除任务 ' + id + ' 吗？')) return;
    fetch('/api/jobs/' + id, { method: 'DELETE' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.ok) {
            showMessage('detailResult', '✅ 任务已删除', 'success');
            document.getElementById('detailCard').classList.add('hidden');
            document.getElementById('reviewCard').classList.add('hidden');
            loadJobList();
        } else {
            showMessage('detailResult', '❌ ' + (data.error || '删除失败'), 'error');
        }
    });
};

// ===================== 轮询 =====================
function startPolling(id) {
    stopPolling();
    pollTimer = setInterval(function() {
        fetch('/api/jobs/' + id)
        .then(function(r) { return r.json(); })
        .then(function(j) {
            if (j.status === 'completed' || j.status === 'failed') {
                stopPolling();
                viewJobDetail(id);
                loadJobList();
                showMessage('detailResult', '✅ 审核完成！结论：' + (j.verdict || '-'), 'success');
            } else {
                showMessage('detailResult', '⏳ 审核中... 状态：' + j.status, 'loading');
            }
        })
        .catch(function() {});
    }, 2000);
}
function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

// ===================== 启动 =====================
loadJobList();

// 如果URL有 job_id 参数，自动打开
var params = new URLSearchParams(window.location.search);
var id = params.get('job_id');
if (id) viewJobDetail(id);
