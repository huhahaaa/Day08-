# 产品负责人交付物实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为“Day08 智能数字媒体内容审核系统”形成一套可指导开发、测试、验收和 8 分钟演示的产品负责人交付物。

**Architecture:** 四份正式文档各自承担单一职责，并通过统一的 `REQ-001` 至 `REQ-010` 需求编号串联。每份文档独立完成内容检查、交叉一致性检查、Git 提交和远程推送。

**Tech Stack:** Markdown、Git、GitHub、PowerShell、Ripgrep

## Global Constraints

- 项目名称固定为“Day08 智能数字媒体内容审核系统”。
- 项目方向固定为方向 A：智能数字媒体内容审核系统。
- 范围为方向 A 完整必做闭环，加一项“审核规则配置化”功能。
- 审核结论统一为“通过 / 待复核 / 不通过”，接口值为 `pass / review / reject`。
- 状态流转统一为 `created -> queued -> running -> completed`，异常进入 `failed`。
- 基础规则采用 `default_rules.json` 中的类别、阈值、证据帧数量和视频采样间隔。
- 未提供成员姓名时，只标注产品、后端、CV、前端、测试角色。
- 只在 `黄林` 分支提交并推送到 `origin/黄林`，不得提交到 `master`。
- 任务书保持未跟踪状态，不加入暂存区。
- 四份正式文档分别形成一个独立 commit，提交后立即推送。

---

## 文件结构

- Modify: `docs/PRD.md`：产品目标、用户、范围、核心流程、业务规则和需求定义。
- Create: `docs/REQUIREMENT_BOARD.md`：按需求编号拆分的角色协作看板。
- Create: `docs/ACCEPTANCE_CHECKLIST.md`：与需求编号一一对应的验收场景和交付检查项。
- Create: `demo/demo_script.md`：8 分钟现场演示脚本、操作路径和异常预案。

### Task 1: 完成产品需求文档

**Files:**
- Modify: `docs/PRD.md`
- Reference: `day08_CV综合项目实战_任务书.md`
- Reference: `default_rules.json`
- Reference: `docs/API.md`

**Interfaces:**
- Consumes: 方向 A 任务书要求、现有 API 路径、默认规则配置。
- Produces: `REQ-001` 至 `REQ-010` 的权威需求定义，供看板和验收清单引用。

- [ ] **Step 1: 写明产品背景、目标和用户角色**

  内容必须包括内容团队依赖人工逐段查看的痛点、机器初筛加人工复核的定位，以及内容审核员、内容负责人、系统维护人员三个用户角色。

- [ ] **Step 2: 固定版本范围和边界**

  本期范围写入上传、异步任务、YOLO 检测、规则评估、证据留档、结果展示、人工复核、历史查询、异常提示和规则配置化；明确排除批量上传、ZIP/CSV 导出和审核版本历史。

- [ ] **Step 3: 定义十项可验收功能需求**

  使用以下编号和标题：

  | 编号 | 标题 |
  |---|---|
  | REQ-001 | 上传素材并创建任务 |
  | REQ-002 | 异步处理与状态查询 |
  | REQ-003 | 图片和视频 YOLO 检测 |
  | REQ-004 | 配置化审核规则与结论 |
  | REQ-005 | 证据帧与审核报告留档 |
  | REQ-006 | 审核结果可视化 |
  | REQ-007 | 人工复核并写回结果 |
  | REQ-008 | 历史任务重开与删除 |
  | REQ-009 | 异常输入和失败提示 |
  | REQ-010 | 页面维护审核规则 |

  每项包含用户故事、前置条件、处理规则和验收标准。

- [ ] **Step 4: 定义审核和状态规则**

  明确风险类置信度不低于 `0.60` 判定不通过，风险或警告检测置信度位于 `0.35` 至 `0.60` 区间进入待复核，未触发规则且处理成功则通过；边界值采用下限包含、上限归入不通过。写明完整任务字段和状态时间戳要求。

- [ ] **Step 5: 补充非功能需求和成功指标**

  包含接口响应一致性、路径安全、失败留档、页面状态完整性、结果可解释性，以及“合法素材闭环成功、异常有明确提示、报告可重读”三个演示成功指标。

- [ ] **Step 6: 验证文档完整性**

  Run:

  ```powershell
  rg -n "待补充|待完善|<!--" docs/PRD.md
  (rg -o "REQ-[0-9]{3}" docs/PRD.md | Sort-Object -Unique).Count
  ```

  Expected: 第一条命令无输出；第二条输出 `10`。

- [ ] **Step 7: 提交并推送 PRD 模块**

  ```powershell
  git branch --show-current
  git add -- docs/PRD.md
  git diff --cached --check
  git commit -m "docs(product): 完善内容审核系统 PRD"
  git push origin "黄林"
  ```

  Expected: 当前分支输出 `黄林`；提交仅包含 `docs/PRD.md`；推送成功。

### Task 2: 完成需求看板

**Files:**
- Create: `docs/REQUIREMENT_BOARD.md`
- Reference: `docs/PRD.md`

**Interfaces:**
- Consumes: PRD 中 `REQ-001` 至 `REQ-010` 的范围和验收标准。
- Produces: 每项需求的优先级、负责人、依赖、交付物、状态和完成定义。

- [ ] **Step 1: 建立看板规则和状态定义**

  使用“未开始 / 进行中 / 待联调 / 待验收 / 已完成 / 受阻”六种看板状态；说明状态必须由产出负责人更新，只有满足完成定义后才能进入已完成。

- [ ] **Step 2: 写入十项需求任务卡**

  看板必须逐项覆盖 `REQ-001` 至 `REQ-010`，为每项指定 P0 或 P1、主责角色、协作角色、前置依赖、代码或文档产出、验收依据和当前状态。`REQ-010` 为 P1，其余闭环需求为 P0。

- [ ] **Step 3: 补充角色产出与单日里程碑**

  角色表覆盖产品、后端、CV、前端、测试；里程碑按上午接口契约和骨架、午间首次联调、下午核心集成、测试修复、最终验收排列。

- [ ] **Step 4: 验证看板覆盖率**

  Run:

  ```powershell
  rg -n "待补充|待完善|<!--" docs/REQUIREMENT_BOARD.md
  (rg -o "REQ-[0-9]{3}" docs/REQUIREMENT_BOARD.md | Sort-Object -Unique).Count
  ```

  Expected: 第一条命令无输出；第二条输出 `10`。

- [ ] **Step 5: 提交并推送需求看板模块**

  ```powershell
  git add -- docs/REQUIREMENT_BOARD.md
  git diff --cached --check
  git commit -m "docs(product): 新增项目需求看板"
  git push origin "黄林"
  ```

  Expected: 提交仅包含 `docs/REQUIREMENT_BOARD.md`；推送成功。

### Task 3: 完成验收清单

**Files:**
- Create: `docs/ACCEPTANCE_CHECKLIST.md`
- Reference: `docs/PRD.md`
- Reference: `docs/REQUIREMENT_BOARD.md`

**Interfaces:**
- Consumes: 十项需求、任务书硬性验收条件和异常测试要求。
- Produces: 产品负责人、测试人员和教师可共同执行的验收基线。

- [ ] **Step 1: 建立验收执行规范**

  说明测试环境、证据要求、通过规则和失败记录方式；所有条目默认保持未勾选，只有实际验证并保存证据后才能勾选。

- [ ] **Step 2: 覆盖十项产品需求**

  每个 `REQ-001` 至 `REQ-010` 至少有一个带前置条件、操作步骤、预期结果和证据类型的验收场景，核心上传、状态、检测、规则、复核和历史查询需包含更细的子项。

- [ ] **Step 3: 写入正常、异常和接口检查**

  正常测试不少于 5 条，异常测试不少于 5 条；明确覆盖合法图片、合法视频、历史重开、人工复核、报告重读、不支持格式、空文件、模型缺失、失败状态和运行中任务删除。接口检查覆盖任务书要求的 8 个方向 A API。

- [ ] **Step 4: 写入页面和交付检查**

  页面检查覆盖加载、空状态、运行、完成、失败和错误提示；交付检查覆盖 README、五份 docs 文档、测试记录、两条 Bug、素材结果、截图、架构图、分工表和 8 分钟演示稿。

- [ ] **Step 5: 验证验收清单覆盖率**

  Run:

  ```powershell
  rg -n "待补充|待完善|<!--" docs/ACCEPTANCE_CHECKLIST.md
  (rg -o "REQ-[0-9]{3}" docs/ACCEPTANCE_CHECKLIST.md | Sort-Object -Unique).Count
  ```

  Expected: 第一条命令无输出；第二条输出 `10`。

- [ ] **Step 6: 提交并推送验收清单模块**

  ```powershell
  git add -- docs/ACCEPTANCE_CHECKLIST.md
  git diff --cached --check
  git commit -m "docs(product): 新增项目验收清单"
  git push origin "黄林"
  ```

  Expected: 提交仅包含 `docs/ACCEPTANCE_CHECKLIST.md`；推送成功。

### Task 4: 完成 8 分钟演示流程

**Files:**
- Create: `demo/demo_script.md`
- Reference: `docs/PRD.md`
- Reference: `docs/ACCEPTANCE_CHECKLIST.md`

**Interfaces:**
- Consumes: 产品目标、主流程、审核规则、验收场景和交付要求。
- Produces: 可由小组成员照稿执行的现场展示流程。

- [ ] **Step 1: 定义演示目标和准备清单**

  准备项包括服务、模型、合法图片、合法视频、异常文件、至少一个完成任务、浏览器窗口和输出目录；强调演示前不得临时修改规则或任务 JSON。

- [ ] **Step 2: 编排 8 分钟演示时间线**

  时间线固定为：项目介绍 45 秒、架构与分工 45 秒、创建任务 60 秒、机器审核 90 秒、结果解释 75 秒、人工复核 60 秒、历史与报告 45 秒、异常处理 30 秒、总结 30 秒，总计 480 秒。

- [ ] **Step 3: 写明逐步操作和讲解词**

  每个环节包含操作者、页面操作、预期画面、关键讲解点和对应需求编号；机器审核必须解释类别、置信度、边界框、阈值和证据帧，人工复核必须展示结论与备注写回。

- [ ] **Step 4: 补充失败预案和现场问答**

  预案覆盖模型加载失败、视频处理过慢、浏览器无法访问和新任务失败；问答覆盖为什么异步、规则如何解释、人工修改如何追溯、如何保证目录删除安全和本项目范围取舍。

- [ ] **Step 5: 验证时间和内容完整性**

  Run:

  ```powershell
  rg -n "待补充|待完善|<!--" demo/demo_script.md
  rg -n "480 秒|模型加载失败|人工复核|REQ-001|REQ-010" demo/demo_script.md
  ```

  Expected: 第一条命令无输出；第二条至少输出 5 行，覆盖总时长、预案、人工复核及首尾需求编号。

- [ ] **Step 6: 提交并推送演示流程模块**

  ```powershell
  git add -- demo/demo_script.md
  git diff --cached --check
  git commit -m "docs(product): 新增八分钟项目演示流程"
  git push origin "黄林"
  ```

  Expected: 提交仅包含 `demo/demo_script.md`；推送成功。

### Task 5: 最终一致性与 Git 交付核验

**Files:**
- Verify: `docs/PRD.md`
- Verify: `docs/REQUIREMENT_BOARD.md`
- Verify: `docs/ACCEPTANCE_CHECKLIST.md`
- Verify: `demo/demo_script.md`

**Interfaces:**
- Consumes: 四份正式交付物和四次模块提交。
- Produces: 产品负责人交付完成的可追溯证据。

- [ ] **Step 1: 核对需求编号一致性**

  ```powershell
  $files = @('docs/PRD.md', 'docs/REQUIREMENT_BOARD.md', 'docs/ACCEPTANCE_CHECKLIST.md')
  foreach ($file in $files) {
      $ids = rg -o "REQ-[0-9]{3}" $file | Sort-Object -Unique
      "$file : $($ids -join ', ')"
  }
  ```

  Expected: 三个文件均输出完整的 `REQ-001` 至 `REQ-010`。

- [ ] **Step 2: 核对分支、远程和提交历史**

  ```powershell
  git branch --show-current
  git status --short
  git log --oneline -6
  git rev-list --left-right --count "origin/黄林...黄林"
  ```

  Expected: 当前分支为 `黄林`；状态中只有未跟踪任务书；最近历史包含规格、计划和四个产品模块提交；远程差异为 `0 0`。
