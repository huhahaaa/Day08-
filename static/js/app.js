/** Day08 智能内容审核工作台 — 前端交互逻辑 */

// ===== 全局状态 =====
const state = {
    currentView: 'task-list',   // 'task-list' | 'review'
    currentJobId: null,
    jobs: [],
};

// ===== DOM 引用 =====
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Day08] 工作台初始化');
    // TODO: 前端团队成员实现 — 加载任务列表、绑定事件
});

// ===== API 调用 =====
const api = {
    async health() {
        // TODO: 前端团队成员实现
    },
    async createJob(formData) {
        // TODO: 前端团队成员实现
    },
    async listJobs() {
        // TODO: 前端团队成员实现
    },
    async getJob(jobId) {
        // TODO: 前端团队成员实现
    },
    async deleteJob(jobId) {
        // TODO: 前端团队成员实现
    },
    async analyzeJob(jobId) {
        // TODO: 前端团队成员实现
    },
    async submitReview(jobId, conclusion, note) {
        // TODO: 前端团队成员实现
    },
    async getReport(jobId) {
        // TODO: 前端团队成员实现
    },
};

// ===== 视图切换 =====
function switchView(view) {
    // TODO: 前端团队成员实现
}

// ===== 事件绑定（预留） =====
// TODO: 前端团队成员实现
