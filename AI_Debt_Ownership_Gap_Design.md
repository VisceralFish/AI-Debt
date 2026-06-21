# AI Debt：Ownership Gap 与 Debt 分析引擎设计文档

> 本文总结 AI Debt 在“理解债 / 认知债 / 所有权债”方向上的核心产品机制：如何判断 AI Coding 过程中哪些内容需要补债、应该补到什么深度，以及如何根据不同 Task 类型使用不同的 Debt 分析引擎。

---

## 1. 核心结论

AI Debt 不应该追踪“AI 做了多少工作”。

在现代 AI Coding 工作流中，用户输入需求，AI 工具通过多轮交互完成设计、编码、修改、测试和修复。按字面统计，绝大多数工作都可以被判定为 AI 完成。如果系统简单追踪“AI 代偿行为”，结论会退化为：

```text
本次 Session 99% 由 AI 代偿。
```

这没有产品价值。

AI Debt 真正应该追踪的是：

> 在 AI 完成 Task 的过程中，哪些关键工程控制点没有被用户确认、理解、验证或掌握，而这些控制点又处在用户当前项目责任边界内。

因此，AI Debt 的核心对象不是 AI Contribution，而是：

```text
Ownership Gap
```

中文可以翻译为：

```text
所有权缺口 / 控制权缺口
```

更准确的产品定位是：

> AI Debt 帮助 AI Builder 判断：哪些东西可以交给 AI 执行，哪些东西必须重新拿回控制权。

---

## 2. 从 Understanding Debt 到 Ownership Debt

传统学习工具关心：

```text
你不会什么知识？
```

AI Debt 应该关心：

```text
这个项目里，哪些东西你名义上拥有，但实际上被 AI 接管了关键控制点？
```

因此，AI Debt 的债务不是普通知识缺口，而是所有权缺口。

完整的 ownership 不只是“理解”，还包括：

```text
能解释
能修改
能调试
能判断
能验证
能负责
```

所以 AI Debt 的债务对象应该定义为：

> 用户交付了一个项目或模块，但其中一部分关键工程控制权并没有真正回到用户手里。

---

## 3. AI Coding 中真正需要关注的不是执行层，而是控制点

AI 负责大量执行工作是正常的。AI Debt 不应把所有 AI 输出都变成债务。

应区分三层：

| 层级 | 含义 | 是否重点追踪 |
|---|---|---|
| Execution 执行层 | 写样板代码、补 import、生成 UI、整理格式 | 通常不追踪 |
| Judgment 判断层 | 方案选择、状态机、数据模型、依赖选择、根因判断 | 重点追踪 |
| Accountability 负责层 | 隐私、安全、支付、数据删除、生产回滚、车规合规 | 高优先级追踪 |

一句话：

> AI 负责执行没问题；AI 替你判断而你无法复核，才是债；AI 替你承担责任但责任实际还在你身上，是最高级债。

---

## 4. Ownership Level：L0-L5 所有权层级

AI Debt 不应默认“AI 替你做了什么，你就必须全部学会”。学习深度应由责任决定，而不是由知识本身决定。

建议使用 L0-L5 所有权层级：

| Level | 名称 | 含义 | 典型验收 |
|---|---|---|---|
| L0 | Ignore | 可以不知道，不进入债务 | 不追踪 |
| L1 | Use | 会用即可，知道入口、配置、基本限制 | 能找到配置和调用入口 |
| L2 | Modify | 能安全修改局部代码或参数 | 能做小改动并说明影响 |
| L3 | Debug | 能定位问题、复现问题、解释修复有效性 | 能复现 bug、解释根因、补回归测试 |
| L4 | Design | 能做方案取舍、理解架构边界 | 能比较替代方案和 trade-off |
| L5 | Assure | 能证明可靠性、安全性、合规性 | 能列失效模式、证据链、验证策略 |

核心原则：

> 抽象层可以上移，但责任层不能消失。

AI 时代，人不需要掌握所有底层细节；但只要某件事仍处在用户责任边界内，用户就需要掌握到足以承担责任的层级。

---

## 5. 学习深度判断：三轴模型

判断一个 Ownership Gap 应补到什么 level，可以使用三轴模型：

```text
Role Responsibility × Change Probability × Failure Cost
```

也就是：

```text
用户是否负责它？
未来是否会改它？
它错了代价有多大？
```

再加两个辅助因素：

```text
Project Criticality
User Familiarity
```

最终形成五个评分维度：

| 维度 | 问题 |
|---|---|
| Role Responsibility | 这是否属于用户当前角色的责任？ |
| Project Criticality | 是否属于项目核心链路？ |
| Change Probability | 未来是否可能频繁修改？ |
| Failure Cost | 出错代价是否高？ |
| User Familiarity Gap | 用户当前是否明显不熟？ |

简化规则：

| 条件 | 建议层级 |
|---|---|
| 不负责、不修改、低风险 | L0 Ignore |
| 只调用、低风险、稳定依赖 | L1 Use |
| 会改代码、中低风险 | L2 Modify |
| 会排障、中高风险 | L3 Debug |
| 涉及架构、产品核心、长期演进 | L4 Design |
| 涉及安全、隐私、支付、数据、合规、车规 | L5 Assure |

---

## 6. Control Contract：控制权契约

为避免系统泛化追踪所有 AI 输出，AI Debt 应引入 Control Contract。

Control Contract 定义：

> 在这个项目中，哪些事情可以交给 AI 自动推进，哪些事情 AI 必须解释，哪些事情必须让用户确认，哪些事情必须补债。

示例：

```text
AI 可自由处理：
- UI 样式微调
- 文案草稿
- 普通 CRUD
- 单测样板

AI 必须解释：
- Session boundary 逻辑
- Debt extraction prompt 结构
- Review task 生成规则
- 数据 schema 变化

AI 必须先确认：
- 删除用户数据
- 上传本地日志
- 引入云端同步
- 改变隐私策略
- 改变核心债务分级模型

用户必须掌握到 L4：
- Ownership Level 判定
- Control Gap 识别
- Session → Debt 的产品链路

用户必须掌握到 L5：
- 隐私数据处理
- 用户代码 / Prompt 是否上传
```

Control Contract 的价值是降低噪音：

```text
不追踪 AI 做了多少；只追踪 AI 是否触碰了用户声明需要保留控制权的区域。
```

---

## 7. User Anchor：用户是否锚定了关键控制点

Ownership Gap 的关键判断标准不是“AI 是否参与”，而是：

```text
用户是否对关键控制点进行了 anchor？
```

用户有 anchor 的信号包括：

```text
用户提出明确约束
用户选择了方案 A 而不是 B
用户要求解释根因
用户要求比较替代方案
用户定义了验收标准
用户手动修改关键逻辑
用户拒绝了 AI 的某个建议
用户指出边界条件
```

用户缺少 anchor 的信号包括：

```text
用户只说“继续 / 可以 / 修一下 / 按你说的来”
AI 自行选择依赖
AI 自行设计状态机
AI 自行定义测试标准
AI 自行修改 schema
AI 自行绕过失败测试
```

如果 AI 推进了关键控制点，而用户没有 anchor，就形成 Ownership Gap 候选。

---

## 8. Ownership Gap 的强信号

第一版不需要识别所有复杂情况，应先抓高置信信号。

### 8.1 未确认的设计选择

AI 自行做出设计选择，例如：

```text
选择状态管理方案
设计状态机
决定数据表结构
决定缓存策略
改变模块边界
```

债务类型：

```text
Unanchored Design Decision
```

### 8.2 未解释的 Bug 修复

AI 修复 bug，但用户没有理解：

```text
为什么错？
怎么复现？
为什么这个 fix 有效？
有没有副作用？
```

债务类型：

```text
Root Cause Ownership Gap
```

### 8.3 高风险文件变更

AI 修改了高风险区域：

```text
auth
payment
privacy
database
migration
session
scheduler
safety
```

债务类型：

```text
Risky File Change
```

### 8.4 新增依赖

AI 引入新依赖或框架，但用户没有确认：

```text
为什么引入？
能不能不用？
版本风险是什么？
替换成本是什么？
许可证和运行时影响是什么？
```

债务类型：

```text
Dependency Ownership Gap
```

### 8.5 验证标准由 AI 自行定义

AI 自己决定测试、验收和边界情况，用户没有参与定义完成标准。

债务类型：

```text
Validation Ownership Gap
```

### 8.6 AI 绕过问题

例如：

```text
catch 掉异常
加 any
disable lint
跳过测试
mock 掉接口
用 setTimeout 避开时序问题
注释掉失败逻辑
```

这类情况常常代表“能跑但不稳”。

---

## 9. Session 分析输出：Top Ownership Gaps

为避免噪音，Session 结束后不应输出完整债务清单，而应限制为：

```text
Top 3 Ownership Gaps
```

或者：

```text
1 个必须补
2 个建议补
若干可忽略
```

示例：

```text
本次 Task 大部分执行工作由 AI 完成，这是正常的。系统只追踪 2 个可能影响你后续控制权的点：

1. 未确认的设计选择：AI 将 Session 结束条件设为 Idle Timeout
为什么重要：这是产品核心边界判断
建议掌握到：L4 Design
补债任务：比较 Idle Timeout / Explicit End / LLM Boundary 三种方案

2. 验证缺口：AI 自行定义了测试场景
为什么重要：误判 Session 会直接影响债务生成质量
建议掌握到：L3 Debug
补债任务：补充 3 个用户仍在工作但 Idle 超时的反例
```

关键是第一句：

```text
大部分执行工作由 AI 完成，这是正常的。
```

AI Debt 不是反 AI，而是管理 AI Delegation。

---

## 10. Cold Start：冷启动阶段应该问什么

冷启动不应是传统技术能力测评，而应建立 Ownership Profile 和 Control Contract。

建议只问 5-8 个问题。

### 10.1 项目目的

```text
快速原型 / Demo
自用工具
准备上线给真实用户
商业产品
工作项目 / 生产系统
安全关键 / 合规相关系统
```

### 10.2 用户角色

```text
独立开发者 / 全栈 Owner
业务功能开发者
底层 / 系统 / 嵌入式开发者
架构设计者
学习者 / 原型验证
产品 / 非工程 Owner
```

### 10.3 目标掌握程度

```text
能用就行
能看懂和小改
能独立维护和排查问题
能重新设计核心方案
能证明可靠性 / 安全性 / 合规性
```

对应 L1-L5。

### 10.4 核心区域

```text
产品核心逻辑
数据模型
架构设计
性能
安全 / 隐私
账单 / 支付
部署 / 运维
UI / 交互
测试 / 质量
底层协议 / 硬件 / 实时性
```

### 10.5 不可接受风险

```text
功能坏了
数据丢了
隐私泄露
用户误解系统建议
成本失控
性能不可接受
后续无法维护
安全事故 / 合规问题
```

### 10.6 AI 控制权偏好

```text
AI 可以自由处理哪些事？
AI 必须解释哪些事？
AI 必须先确认哪些事？
哪些事用户必须深度掌握？
```

冷启动输出：

```ts
interface OwnershipProfile {
  role: string
  projectIntent: string
  targetOwnershipLevel: 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
  criticalAreas: string[]
  unacceptableRisks: string[]
  controlContract: ControlContract
  techFamiliarity: Record<string, 'low' | 'medium' | 'high'>
}
```

---

## 11. 持续跟踪与迭代

冷启动只提供先验；真正的判断应通过 Session 持续校准。

### 11.1 用户反馈校准

每条 Ownership Gap 旁边提供轻量反馈：

```text
太浅了 / 合适 / 太深了 / 不相关
```

系统据此调整该项目、该技术、该模块的权重。

### 11.2 验证任务完成情况

如果用户完成 L3 Debug 任务，系统可以上调用户当前估计能力。

```text
完成复现 bug
完成根因解释
完成回归测试
完成安全修改
```

### 11.3 重复求助信号

如果用户反复询问同一模块、同一概念、同一类错误，说明当前估计掌握层级可能偏高，应下调。

### 11.4 AI 高频修改热区

如果某核心模块持续由 AI 修改，而用户没有完成任何补债任务，应生成高优先级 Ownership Drift 提醒。

```text
该模块已经成为高 AI 介入区域，且属于核心链路。建议补到 L4。
```

### 11.5 Bug 回流

如果后续 bug 出现在之前 AI 生成或 AI 修改区域，应提高该区域 Failure Cost 和 Debug 要求。

### 11.6 项目阶段变化

项目从 Demo 进入 Beta、生产、商业化或真实用户阶段后，相关模块的 Required Level 应自动上调。

---

## 12. Task 类型：需要可见，但不应成为用户负担

Task 类型对系统必须显式，因为不同 Task 类型需要不同 Debt 分析引擎。

但对用户而言，Task 类型应该：

```text
轻量展示
自然语言命名
允许纠正
用于解释 Debt 来源
```

推荐用户可见类型：

| 用户可见类型 | 内部类型 | 用户理解 |
|---|---|---|
| 新增模块 | Creation | 从零创建新能力 |
| 旧模块维护 | Maintenance | 修改已有逻辑、修 bug、补功能 |
| 新旧接入 | Integration / Mixed | 新模块接入已有系统 |
| 重构整理 | Refactor | 行为基本不变，调整结构 |
| 实验探索 | Experiment / Spike | 原型、试验、验证想法 |

示例 UI：

```text
本次工作看起来是：新旧接入
原因：新增了 review-task-generator.ts，同时修改了 session-analyzer.ts 和 debt-ledger.ts。

[修改工作类型]
```

用户必须能够纠正系统判断。例如：

```text
系统判断：新增模块
用户修正：重构整理
```

因为新增大量文件可能只是拆分旧模块，而不是创建新功能。

---

## 13. 多 Debt 分析引擎架构

“新增文件 / 新开发模块”和“旧模块维护”不应使用同一套 Debt 分析逻辑。

两者风险来源不同：

```text
新增模块的问题：你是否理解 AI 帮你创造出来的结构？
旧模块维护的问题：你是否理解 AI 对既有系统造成了什么影响？
```

因此建议使用：

```text
共享底座 + 多分析器架构
```

---

## 14. Creation Debt Engine：新增模块分析引擎

新增模块的债务本质是：

```text
Creation Ownership Debt
```

即：新资产虽然进入了你的项目，但其结构、边界、设计理由是否真正属于你？

Creation Engine 重点分析：

| 控制点 | 典型问题 |
|---|---|
| 模块职责 | 这个模块负责什么，不负责什么？ |
| 模块边界 | 它与哪些模块交互？边界是否清晰？ |
| 数据模型 | 为什么这样设计？是否可演进？ |
| 状态机 / 生命周期 | 有哪些状态？状态如何迁移？ |
| 错误处理 | 失败时如何退化、重试、提示、回滚？ |
| 依赖选择 | 为什么引入这些依赖？能否替换？ |
| 测试策略 | 如何证明这个模块行为正确？ |
| 可维护性 | 未来如何扩展？哪些地方最容易改坏？ |

Creation 补债任务：

```text
画模块边界图
解释新数据结构
列失败路径
设计扩展场景
比较替代方案
写最小重建版本
```

---

## 15. Maintenance Debt Engine：旧模块维护分析引擎

旧模块维护的债务本质是：

```text
Change Impact Debt
```

即：AI 的修改是否破坏了原模块的意图、约束、调用契约和历史原因？

Maintenance Engine 重点分析：

| 控制点 | 典型问题 |
|---|---|
| 原有行为 | 修改前这个模块如何工作？ |
| 变更意图 | 这次修改真正要解决什么？ |
| 调用契约 | 输入输出、异常、返回值是否变化？ |
| 状态兼容 | 是否影响已有状态或历史数据？ |
| 数据兼容 | schema / migration / serialization 是否受影响？ |
| 调用方影响 | 哪些上游 / 下游会受影响？ |
| 测试覆盖 | 原有测试是否需要更新？ |
| 回归风险 | 哪些旧场景可能被改坏？ |
| 根因闭环 | bug fix 是否解决根因，而不是绕过？ |
| 隐含约束 | 是否破坏了历史上未写明的设计原因？ |

Maintenance 补债任务：

```text
解释修改前后行为差异
列调用方影响
复现原 bug
补回归测试
说明为什么 fix 有效
设计回滚方案
```

---

## 16. Integration Debt Engine：新旧接入分析引擎

现实中很多任务是 Mixed：新增模块，同时接入旧系统。

这种任务同时存在三类风险：

```text
Creation Debt：新模块设计是否理解？
Change Debt：旧系统接入是否安全？
Integration Debt：新旧边界是否稳定？
```

Integration Engine 重点分析：

```text
新模块如何接入旧系统
接口契约是否清晰
数据流是否改变
错误是否会跨模块传播
旧行为是否被破坏
新模块失败时旧系统如何降级
```

Integration 补债任务：

```text
画新旧模块数据流
列接口契约
模拟新模块失败
检查旧行为兼容
写端到端测试
```

---

## 17. Refactor Debt Engine：重构分析引擎

重构任务声称：

```text
行为不变，只改变结构。
```

因此 Refactor Engine 重点分析：

```text
行为是否真的不变？
抽象是否更清楚？
有没有引入过度设计？
测试是否足以证明等价？
```

Refactor 补债任务：

```text
证明行为等价
列抽象收益和成本
检查是否过度设计
确认测试覆盖旧行为
```

长期看，AI Debt 应至少支持四类分析器：

```text
Creation：新增能力
Maintenance：修旧能力
Integration：接入新旧边界
Refactor：改变结构但声称行为不变
```

MVP 可以先实现 Creation / Maintenance / Mixed。

---

## 18. 系统架构建议

建议采用共享底座 + 专用分析器：

```text
Shared Pipeline
  - Session ingest
  - Diff parser
  - File classifier
  - Project map
  - Control Contract
  - Ownership Level scorer

Specialized Analyzers
  - CreationDebtAnalyzer
  - MaintenanceDebtAnalyzer
  - IntegrationDebtAnalyzer
  - RefactorDebtAnalyzer
```

接口示例：

```ts
interface DebtAnalyzer {
  supports(task: TaskContext): boolean
  analyze(
    task: TaskContext,
    project: ProjectContext,
    profile: OwnershipProfile
  ): DebtCandidate[]
}

class CreationDebtAnalyzer implements DebtAnalyzer {}
class MaintenanceDebtAnalyzer implements DebtAnalyzer {}
class IntegrationDebtAnalyzer implements DebtAnalyzer {}
class RefactorDebtAnalyzer implements DebtAnalyzer {}
```

Task Router 根据任务类型调用对应 analyzer：

```ts
const analyzers = registry.filter(analyzer => analyzer.supports(taskContext))

const candidates = analyzers.flatMap(analyzer =>
  analyzer.analyze(taskContext, projectContext, ownershipProfile)
)

return rankAndDedupe(candidates).slice(0, 3)
```

---

## 19. Task Router：任务类型路由

MVP 可以先用简单规则：

```text
如果新增文件占比高，且旧文件修改少：Creation
如果主要修改已有文件：Maintenance
如果新增文件和旧文件都较多：Mixed / Integration
如果用户目标包含 refactor / clean up / extract / reorganize：Refactor
如果是 spike / demo / prototype：Experiment
```

伪代码：

```ts
function classifyTask(diff: DiffSummary): TaskMode {
  const addedFiles = countAddedFiles(diff)
  const modifiedFiles = countModifiedFiles(diff)

  if (containsRefactorIntent(diff.summary)) return 'refactor'
  if (addedFiles >= 2 && modifiedFiles <= 1) return 'creation'
  if (addedFiles > 0 && modifiedFiles > 0) return 'mixed'
  if (modifiedFiles >= 1) return 'maintenance'

  return 'maintenance'
}
```

但最终不能只靠文件数量，还要结合用户意图、diff 语义和项目结构。

---

## 20. Debt Item 数据结构建议

```ts
interface DebtItem {
  id: string
  projectId: string
  sessionId: string

  title: string
  summary: string

  taskContext: {
    taskType: 'creation' | 'maintenance' | 'integration' | 'refactor' | 'experiment'
    userVisibleLabel: string
    confidence: number
  }

  ownershipGap: {
    controlPoint: string
    gapType:
      | 'unanchored_design_decision'
      | 'root_cause_gap'
      | 'risky_file_change'
      | 'dependency_gap'
      | 'validation_gap'
      | 'workaround_gap'
      | 'integration_gap'
      | 'refactor_equivalence_gap'
    reason: string
    evidence: Evidence[]
  }

  ownershipLevel: {
    requiredLevel: 'L0' | 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
    currentEstimatedLevel: 'L0' | 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
    scoreBreakdown: {
      roleResponsibility: number
      projectCriticality: number
      changeProbability: number
      failureCost: number
      familiarityGap: number
    }
  }

  repayment: {
    taskType:
      | 'explain_back'
      | 'modify_safely'
      | 'reproduce_bug'
      | 'break_test'
      | 'rebuild_minimal'
      | 'compare_alternatives'
      | 'assurance_check'
    task: string
    validationCriteria: string[]
  }

  status: 'open' | 'ignored' | 'accepted' | 'in_progress' | 'verified'
}
```

债务大小可以定义为：

```text
Debt Gap = Required Ownership Level - Current Estimated Ownership Level
```

---

## 21. MVP 切分建议

### V0.1

实现：

```text
5 问冷启动
Control Contract 初始配置
Task 类型粗分类：Creation / Maintenance / Mixed
Top 3 Ownership Gaps
L0-L5 Required Level 判定
每条债 1 个补债任务
用户反馈：太浅 / 合适 / 太深 / 不相关
```

优先识别 5 类高置信 Gap：

```text
Unconfirmed Design Decision
Unexplained Bug Fix
Risky File Change
Dependency Introduction
Validation Gap
```

### V0.2

新增：

```text
Refactor 检测
Task 类型用户纠正
Debt Aging
AI Compensation Heatmap
```

### V0.3

新增：

```text
Project Map
调用关系分析
模块 criticality 自动推断
Bug 回流校准
Ownership Drift 周报
```

---

## 22. 推荐产品语言

建议 AI Debt 内部和 UI 使用以下概念：

| 概念 | 含义 |
|---|---|
| Ownership Gap | 所有权 / 控制权缺口 |
| Control Contract | 控制权契约 |
| User Anchor | 用户对关键控制点的确认、选择、约束或验证 |
| Required Ownership Level | 当前项目要求用户掌握到的层级 |
| Current Ownership Level | 系统估计用户当前掌握层级 |
| Task Control Report | Session 后的控制点报告 |
| Creation Debt | 新增模块产生的设计所有权债 |
| Change Impact Debt | 旧模块维护产生的影响面控制债 |
| Integration Debt | 新旧模块接入产生的边界债 |
| Refactor Debt | 重构产生的行为等价与抽象债 |
| Ownership Recovery | 通过项目内任务恢复控制权 |

推荐对外表达：

```text
Track what AI changed. Recover what you need to own.
```

中文：

```text
记录 AI 改变了什么，追回你必须掌握的控制权。
```

或者：

```text
追回关键控制权，而不是追回所有实现细节。
```

---

## 23. 最终总结

AI Debt 的核心不应是“AI 替我做了多少”，而是：

```text
AI 在完成 Task 的过程中，是否接管了用户仍需负责的关键控制点？
```

因此，系统主线应从：

```text
AI 代偿行为识别
```

升级为：

```text
Ownership Gap 识别与恢复
```

最终产品链路：

```text
Ownership Profile
↓
Control Contract
↓
Session / Task 采集
↓
Task 类型路由
↓
专用 Debt Analyzer
↓
Top Ownership Gaps
↓
Required Level 判定
↓
项目内补债任务
↓
用户反馈与持续校准
```

一句话定义：

> AI Debt 是一个面向 AI Builder 的控制权恢复系统：它不要求用户理解所有 AI 生成细节，而是帮助用户识别并补回那些仍处在自己责任边界内的关键 Ownership Gap。
