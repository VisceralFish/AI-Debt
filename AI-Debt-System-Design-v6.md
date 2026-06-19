# AI Debt 系统设计文档（v6）

> v6 更新说明：本版基于 v5 文档继续修订。核心变化包括：
>
> 1. 产品战略采用 **V3 收敛版**：AI Debt 聚焦认知债，不主打技术债扫描。
> 2. 交互体系吸收 **V2 多模式设计**：保留 L0-L4，支持从静默记录到系统学习路径的分级切换。
> 3. 最终产品公式调整为：**默认干中记，按需干中学，事后集中学**。
> 4. 触发模型从 `SessionEnd-first` 调整为 **Journal-first + Stop 轻分析 + Idle Timeout 深分析**。
> 5. 将 **Ambient Companion UI / Pet UI** 收敛为 **Terminal-embedded Companion**：MVP 优先采用嵌入终端的低打扰气泡 / 状态卡片，而非跨平台浮动桌宠。
> 6. 明确：Terminal Companion 只是 L0/L1/L2 的入口层；AI Debt Core 才是认知债分析、Ledger、Inbox、Grasp Check 的系统核心。
> 7. 补充 claude-minipet、Petdex、OpenPets 的实现复杂度对比：claude-minipet 更贴 Claude Code TUI，但不天然多工具；Petdex/OpenPets 多工具/桌面生态更强，但 MVP 复杂度更高。
> 8. 新增 **Cold Start & Adaptive Learning Profile**：用 2 分钟冷启动建立初始角色/深度/打扰偏好，再通过项目、Session 行为、Grasp Check 和债务偿还历史持续校准。

---

# 0. 一句话结论

**AI Debt 是一个面向 AI Builder 的认知债管理工具。**

它在用户使用 Claude Code、Codex、Cursor、ChatGPT 等 AI 工具进行 Build、Debug、Refactor、Design 的过程中，静默捕获 Session、Diff、Tool Call、错误日志和关键决策，识别 AI 代劳造成的认知债、理解债与意图债，并在 Idle Timeout / Pending Review 后通过分级复盘、Learning Inbox、Grasp Check 和长期 Debt Ledger，帮助 Builder 在保持 AI 提效的同时不丢失自身理解能力。

更短的定义：

```text
AI Debt = 默认干中记 + 按需干中学 + 事后集中学
```

工程化表达：

```text
AI Debt = Journal-first + Adaptive Profile + Learn-on-demand + Review-after-build
```

英文定位：

```text
AI Debt is a session-level cognitive debt tracker for AI-assisted builders.
It records what AI did on your behalf, what you still don't understand,
and helps you pay down that debt when the build context cools down.
```

中文定位：

```text
AI Debt 是 AI Builder 的 Session 级认知债账本。
它记录 AI 替你完成了什么，也记录你还没真正理解什么。
```

核心边界：

```text
AI Debt does not primarily ask whether the code has debt.
It asks whether you do.
```

中文：

```text
AI Debt 不主要问代码有没有债，而是问：你有没有欠下理解债。
```

---

# 1. v2 / v3 / v4 / v5 与当前 v6 设计的差异检查

## 1.0 v6 融合结论

v2 的优势是 L0-L4 多模式和轻量 Just-in-time Learning，用户价值感更强；v3 的优势是产品战略更锋利，避免滑向普通 AI Tutor 或技术债扫描器。

v6 不在 v2/v3/v4/v5 之间二选一，而采用：

```text
战略上采用 v3：认知债为核心，技术债只作为信号。
交互上吸收 v2：保留 L0-L4 分级学习入口。
触发上新增修正：不依赖用户主动 End Session，而采用 Stop + Idle Timeout。
前台体验上收敛为 Terminal Companion：用终端嵌入式低打扰气泡承载 Pending Review。
冷启动上采用 Adaptive Profile：先由用户给出初始定位，再通过真实 AI Build 行为持续校准。
```

一句话：

```text
默认干中记，按需干中学，事后集中学。
```

---

## 1.1 产品形态差异

v2 文档中仍然带有较强的 “Just-in-time Learning / 边做边学” 气质：

```text
当用户有时间时，提供 Just-in-time Learning；
当用户没时间时，记录 Learning Debt。
```

这在理念上成立，但作为主产品形态存在风险：真实 AI Builder 工作流中，用户优先目标通常是交付、修复、跑通、提交，而不是在构建过程中被持续教学打断。

v3 调整为：

```text
主形态：干中记，事后学。
辅助机制：高风险或重复认知债时，进行轻量干中提示。
```

也就是说，AI Debt 不是实时教学助手，而是：

```text
AI Build 过程中的认知债黑匣子 + 事后学习系统。
```

---

## 1.2 债务对象差异

v2 中仍然多次将技术债、理解债、学习债并列处理。虽然已有“主打认知债，不主打代码技术债”的表述，但整体结构里仍保留了较多技术债分析色彩。

当前设计进一步收敛：

```text
技术债不是核心产品对象。
技术债只是认知债判断的辅助信号。
```

原因：

1. AI 时代，显性技术债会越来越适合由 AI reviewer、静态分析器、测试生成器、SAST、代码质量平台扫描。
2. 真正危险的是 AI 代劳后用户没有理解系统意图、设计边界、错误路径和调试方法。
3. 认知债不能简单外包给 AI，因为真正掌握需要用户能复述、修改、debug、迁移和独立判断。

因此 v3 采用：

```text
Technical Debt as Signal.
Cognitive Debt as Product.
```

中文：

```text
AI Debt 把技术债当信号，把认知债当产品核心。
```

---

## 1.3 竞品调研差异

v2 已经调研了 cognitive-coverage、why-plugin、cognitive-debt-prevention-kit、cognitive-debt-guard、ai-debt-scanner、ai-session、claude-review-loop 等项目。

但 v2 漏掉了一个重要项目：

```text
aditya-rajesh2006/AIDebtLens
```

该项目定义完整，且与 AI Debt 在命名、AI-generated code debt、technical debt、cognitive debt scoring 等方向高度重合。v3 必须补充该项目，并重新明确差异化。

修正后的结论：

```text
不是“没有完整产品定义接近的项目”，
而是“已有 repo/file 级 AI Debt Lens 项目，
但尚未覆盖 session-level cognitive debt ledger + 事后学习系统”。
```

---

## 1.4 模块结构差异

v2 中的模块偏向：

```text
Session Analyzer
Concept Extractor
AI Delegation Auditor
Debt Scorer
Quiz Generator
Debrief Generator
Learning Ledger
```

这些模块仍然保留，但 v3 需要从用户体验链路重新组织为：

```text
Build Trace          # 干中记
Cognitive Debt Mark  # 标记认知债
Session Review       # 事后筛
Learning Inbox       # 延迟学习入口
Grasp Check          # 掌握度验证
Debt Ledger          # 长期账本
Manual Mode          # 不依赖 AI 的复现练习
```

---

# 2. 背景与问题定义

## 2.1 AI Builder 的新矛盾

AI 编程与 Agent 工具显著提升了 Builder 的交付速度。用户可以通过 Claude Code、Codex、Cursor、ChatGPT 等工具快速完成：

- 代码生成
- Bug 修复
- 架构设计
- 文档撰写
- 技术调研
- 测试补全
- 脚本编写
- 产品方案推演
- Agent / MCP / Plugin 系统构建

但效率提升会产生一个新的结构性问题：

> 用户完成了任务，但不一定真正掌握了完成任务过程中涉及的推理、判断、边界和意图。

典型情况：

1. AI 修改了代码，但用户没有理解改动背后的状态机、边界条件或失败路径。
2. AI 给出了架构方案，但用户没有理解为什么这样分层、为什么不用替代方案。
3. AI 引入了工具、框架、库、协议，但用户只是接受了结果。
4. AI 修复了错误，但用户没有理解根因和定位路径。
5. AI 给出了命令和脚本，但用户不知道为什么执行这些命令。
6. 用户在工作场景下没有时间学习，只能先完成交付。
7. 多次 AI 代劳后，用户逐渐丧失对系统的解释权和维护能力。

这不是传统技术债问题，而是 **认知债问题**。

---

## 2.2 认知债定义

**认知债（Cognitive Debt）** 指用户在 AI-assisted build 过程中，由于接受了 AI 生成的代码、设计、解释、修复或决策，但没有真正理解其原理、边界、意图和维护方法，而欠下的理解与判断债务。

可以用一句话描述：

```text
AI 帮你 build 了东西，但你还没有真正 grasp 它。
```

认知债的表现包括：

| 类型 | 描述 |
|---|---|
| 概念债 | 知道概念名，但不能解释边界和适用场景 |
| 代码债 | 能运行代码，但不能解释实现逻辑和失败路径 |
| 架构债 | 接受了架构分层，但不能说明为什么这样设计 |
| 工具债 | 会使用命令或工具，但不知道其机制和副作用 |
| 调试债 | AI 修好了 bug，但用户无法复现定位过程 |
| 意图债 | 设计为什么存在、为什么不是另一种方案，没有被用户掌握或外部化 |
| 维护债 | 代码上线后坏了，用户不知道该从哪里下手 |

---

## 2.3 技术债与认知债的关系

传统技术债主要存在于代码、架构、测试和维护成本中。

认知债主要存在于人的理解、判断和系统意图中。

二者关系：

```text
技术债：代码里留下的问题。
认知债：人脑里缺失的理解。
意图债：系统为什么这样设计没有被外部化。
```

AI Debt 的核心判断：

```text
技术债是表层症状，认知债是上游病灶。
```

AI Debt 不应主打技术债扫描。技术债在系统里只作为辅助信号：

- AI 大量生成代码
- 关键路径被修改
- 错误处理被补全
- 测试缺失
- 复杂度升高
- 安全敏感区域发生变化
- 架构边界被改动
- 并发 / 状态机 / 数据迁移路径被 AI 处理

这些信号不直接作为核心输出，而是触发认知债判断：

```text
检测到 AI 修改了 auth refresh flow，且没有看到用户追问失败路径。
可能产生认知债：用户未验证 token refresh failure path。
```

---

## 2.4 本系统要解决的问题

AI Debt 要解决的核心问题不是“AI 写的代码是否优雅”，而是：

> 用户在 AI Build 过程中，哪些推理、判断和实现被 AI 代劳了？
> 用户是否真正理解？
> 如果暂时不理解，如何记录、复盘并最终偿还？

核心问题包括：

| 问题 | 描述 |
|---|---|
| AI 代劳不可见 | 用户不知道哪些关键思考是 AI 替自己完成的 |
| 认知债即时消失 | Session 关闭后，理解缺口随对话一起蒸发 |
| 工作中无学习时间 | 用户当前只想交付，不想被教学打断 |
| 自评理解不可靠 | 用户以为自己懂了，但无法复述、修改或 debug |
| 重复债务未聚合 | 同一认知薄弱点多次出现，但没有形成长期提醒 |
| 意图未外部化 | AI 给了方案，但设计理由和约束没有沉淀 |
| AI 越用越依赖 | 产出速度提高，但自身判断力和维护能力下降 |

---

# 3. 产品定位

## 3.1 不是什么

AI Debt 不是：

- 普通知识库
- 普通课程系统
- 普通会话总结器
- 普通 AI Tutor
- 普通代码质量扫描器
- 普通技术债 dashboard
- 普通 Anki 卡片生成器
- 实时教学助手

---

## 3.2 是什么

AI Debt 是：

> AI Build 过程中的认知债黑匣子 + 按需学习系统。

更具体：

> 一个 Local-first 的 Session 级认知债管理工具，通过 Hook 自动采集 AI Build 过程，通过 MCP 暴露分析与账本能力，通过 Skill/Command 完成轻量交互，通过 Debt Ledger 管理长期认知债状态。

---

## 3.3 核心体验

```text
干中记
按需学
事后看
反复出现就提醒
真正掌握后销账
```

对应系统链路：

```text
AI Build 中
  ↓
L0 静默记录 / Build Journal
  ↓
Stop 轻分析 / 候选认知债
  ↓
Idle Timeout 深分析 / Pending Review
  ↓
L1 30 秒速记
  ↓
用户按需进入 L2 / L3 / L4
  ↓
Grasp Check
  ↓
Debt Resolved
```

---

# 4. 设计原则

## 4.1 默认干中记，按需干中学，事后集中学

AI Debt 的主形态不是实时教学助手，而是“干中记”为默认、“干中学”为可选、“事后学”为主要偿还入口。

原因：

- Builder 使用 AI 的首要目标通常是交付。
- 实时教学会打断开发流。
- 认知债可以先记录，不必当场偿还。
- 用户有兴趣时可以主动进入 L2/L3/L4。
- 真正有价值的是在合适时机复盘和偿还。

核心原则：

```text
Build now.
Capture debt continuously.
Learn on demand.
Review when the context cools down.
```

中文：

```text
现在先做，但别让理解债消失；有空时再偿还。
```

---

## 4.2 默认不打扰

系统默认不应该强制教学，而应该：

- 静默记录
- 只提示高优先级认知债
- 提供轻量入口
- 用户主动进入深度学习时才展开
- 高风险场景才进行即时提醒

核心原则：

```text
学习不能成为交付阻塞项，但认知债必须被记录。
```

---

## 4.3 技术债只作为信号

系统不主打技术债扫描。

技术债信号的作用是帮助判断认知债：

```text
复杂代码变化 → 可能存在理解债
关键路径被 AI 修改 → 可能存在维护债
错误处理被 AI 生成 → 可能存在失败路径理解债
测试缺失 → 可能存在验证债
```

但最终输出应该是：

```text
你是否理解 AI 帮你改了什么？
你是否知道哪里会坏？
你是否能在 AI 不在时 debug？
```

---

## 4.4 分级学习，但不实时教学

保留 L0-L4 分级，但它们主要用于 Session 后和学习 Inbox，不用于强实时教学。

| 等级 | 名称 | 使用时机 |
|---|---|---|
| L0 | Silent Capture | 构建中默认记录，不展示 |
| L1 | 30 秒速记 | Idle Timeout / Pending Review 后快速浏览 |
| L2 | 3 分钟轻量学习 | 用户选择“学一个重点” |
| L3 | 15 分钟深度学习 | 下班后/周末/主动深挖 |
| L4 | 系统性学习路径 | 某类认知债长期重复出现 |

---

## 4.5 有证据才记债

认知债不能靠模型随便猜。

每一条 Cognitive Debt Item 必须包含 evidence：

```text
AI 替用户完成了什么？
用户是否追问？
用户是否验证？
是否修改了关键路径？
是否缺少测试？
是否重复出现？
```

没有 evidence 的债务不进入 Ledger。

---

## 4.6 认知债可偿还

认知债不是知识点收藏，而是可以被偿还的债务。

偿还标准不是“看过解释”，而是通过 Grasp Check：

```text
能复述
能修改
能 debug
能解释取舍
能迁移到新场景
能在 AI 不在时复现关键逻辑
```

---

# 5. 目标用户与使用场景

## 5.1 目标用户

| 用户类型 | 需求 |
|---|---|
| 独立开发者 | 用 AI 快速做产品，同时避免自己失去系统掌控 |
| 软件工程师 | 工作中使用 AI 修问题、写代码，但不想欠下无法维护的理解债 |
| AI Builder | 构建 Agent、MCP、Plugin、Workflow 时，需要持续掌握底层判断 |
| 产品型工程师 | 需要理解 AI 生成方案背后的技术和产品取舍 |
| 团队 Tech Lead | 关心团队是否在 AI 交付中形成隐性认知债 |

---

## 5.2 场景一：工作中修 Bug

用户通过 Claude Code 修复复杂 bug。

Session 中：

- AI 查看日志
- AI 修改状态机恢复逻辑
- AI 生成测试
- 用户接受修改并继续跑验证

AI Debt 行为：

- 静默记录 transcript、diff、tool calls、error logs
- 标记潜在认知债：状态机恢复策略由 AI 代劳
- Idle Timeout / Pending Review 后给 30 秒速记
- 用户没时间则加入 Learning Inbox

输出示例：

```text
本次记录到 2 个认知债：

P1：状态机恢复策略理解债
原因：AI 修改了 bus recovery 逻辑，但用户没有追问失败分支。

P2：测试断言理解债
原因：AI 生成了测试，但用户没有确认断言覆盖的边界。

[跳过并记录] [30 秒速记] [学一个重点] [深度复盘]
```

---

## 5.3 场景二：设计 Agent 系统

用户和 AI 讨论 MCP、Hook、Skill、Subagent 的系统架构。

AI Debt 行为：

- 记录 AI 给出的架构分层判断
- 标记认知债：Hook / Skill / MCP 边界
- 将其与历史相似债务聚合
- 如果 seen_count >= 3，提示用户建议偿还

输出示例：

```text
你已经第 3 次遇到 Hook / Skill / MCP 边界问题。
建议花 3 分钟偿还这个认知债。
```

---

## 5.4 场景三：周末复盘

用户运行：

```bash
ai-debt inbox
```

系统输出：

```text
你本周共有 14 条认知债，其中 3 条重复出现。

建议今天处理 1 条：
Hook / Skill / MCP 边界

原因：
- 出现 4 次
- 与当前 AI Debt 架构设计强相关
- 未掌握会导致插件、Hook、MCP 职责混乱
```

---


# 6. Cold Start & Adaptive Learning Profile（v6 更新）

## 6.1 设计目标

AI Debt 的冷启动不应该试图一次性“测准用户是谁”。用户在 AI 时代的真实身份通常是混合型：同一个人可能在一个项目里是软件工程师，在另一个项目里是产品设计者，在第三个项目里是 AI Agent Builder。

因此，冷启动的目标不是给用户贴一个永久标签，而是建立一个可更新的初始假设：

```text
Cold Start = 显式自选 + 项目信号 + 行为校准 + 轻量测验
```

一句话：

```text
AI Debt 不需要一开始知道用户是谁；
它只需要知道用户当前在 build 什么、希望掌握到什么程度、愿意被打扰到什么程度。
```

最终画像应由两部分组成：

```text
Initial Profile = Self-declared Role + Current Project Signals + Mastery Target + Interruption Preference

Adaptive Profile = Initial Profile + Session Behavior + Grasp Check Results + Debt Resolution History
```

---

## 6.2 用户定位：多标签，而不是单一角色

AI Debt 应支持多标签用户定位：

```json
{
  "primary_role": "AI Agent Builder",
  "secondary_roles": ["Software Engineer", "Product Builder"],
  "current_context": "Designing MCP + Hook + Skill workflow"
}
```

### 6.2.1 主定位候选

| 定位 | 典型场景 | AI Debt 应重点追踪 |
|---|---|---|
| Software Engineer | 写代码、Debug、重构、测试 | 代码理解债、架构判断债、调试根因债 |
| Full-stack Builder | 前端、后端、数据库、部署、产品都做 | 跨层理解债、系统边界、集成风险 |
| Product Builder | PRD、原型、用户路径、产品取舍 | 需求判断债、用户假设债、方案取舍债 |
| AI Agent Builder | MCP、Hook、Skill、Agent workflow | 工具链边界、Agent 架构、自动化风险 |
| Research / Analysis Builder | 调研、论文、竞品、策略分析 | 证据链、概念理解、推理链债 |
| Designer / Creative Builder | 视觉、交互、内容、叙事 | 审美决策、设计原则、风格系统债 |

MVP 阶段优先支持：

```text
Software Engineer
Full-stack Builder
AI Agent Builder
Product Builder
```

---

## 6.3 冷启动问题：控制在 4-5 个以内

冷启动不应做成长问卷。每个问题必须直接影响后续系统行为。

### Q1：你主要用 AI 辅助完成哪类工作？

```text
可多选：
[ ] 写代码 / Debug / 重构
[ ] 全栈产品开发
[ ] AI Agent / MCP / 自动化工具
[ ] 产品设计 / PRD / 用户路径
[ ] 技术调研 / 方案分析
[ ] 创意内容 / 设计 / 原型
```

影响：决定 concept taxonomy、债务分类、Grasp Check 类型。

---

### Q2：你当前更像哪种 Builder？

```text
A. 专业工程师：需要保证质量、可维护性和可解释性
B. 独立开发者：希望快速做出产品，同时补齐关键知识
C. 产品型 Builder：更关心需求、用户、方案和落地
D. AI 工具构建者：主要在做 Agent、MCP、自动化系统
E. 学习型 Builder：希望通过 AI 项目系统提升能力
```

影响：决定默认提示策略和债务优先级。

---

### Q3：你希望掌握到什么颗粒度？

不要问“你想学多深”，而要问“你希望自己最终能做到什么”。

```text
对于 AI 帮你完成的内容，你通常希望掌握到哪一级？

D1. 知道：知道这个概念存在，大概用于什么
D2. 能解释：能用自己的话讲清楚关键逻辑
D3. 能修改：能在 AI 生成结果基础上独立改动
D4. 能 Debug：出问题时知道从哪里开始查
D5. 能设计：能比较替代方案，独立做架构取舍
```

内部字段：

```json
{
  "mastery_depth": "debug"
}
```

注意：这里的 D1-D5 是“掌握颗粒度”，不要和 AI Debt 的 L0-L4 学习模式混淆。

---

### Q4：工作中你希望被打扰到什么程度？

```text
A. 尽量不打扰，只记录
B. Session 空闲后给 30 秒复盘
C. 关键点可以轻提示
D. 我愿意边做边学
```

映射关系：

| 选择 | 默认行为 |
|---|---|
| A | L0 静默记录 |
| B | L1 Idle Pending Review |
| C | L1 + 高优先级 L2 入口 |
| D | L2 默认可展开 |

建议默认值：

```text
B. Session 空闲后给 30 秒复盘
```

---

### Q5：你最不希望 AI 替你做完但自己没掌握的是什么？

```text
[ ] 代码逻辑
[ ] Bug 根因
[ ] 架构设计
[ ] 工具链 / 框架
[ ] 产品需求判断
[ ] 方案取舍
[ ] 安全 / 权限 / 数据风险
[ ] 测试与验证
```

影响：决定 debt scoring 权重。

例如用户选择“Bug 根因”和“架构设计”，当 Session 中出现 AI root cause analysis 或 architecture decision 时，认知债优先级提高。

---

## 6.4 掌握颗粒度 D1-D5

AI Debt 的掌握颗粒度不应使用“浅 / 中 / 深”这种模糊表达，而应使用可验证的工程能力分级。

| 级别 | 名称 | 判断标准 | 适用内容 |
|---|---|---|---|
| D1 | Aware / 知道 | 知道概念存在和大概用途 | 背景知识、低频工具 |
| D2 | Explain / 能解释 | 能用自己的话解释为什么存在、解决什么问题 | 产品、架构、方案讨论 |
| D3 | Modify / 能修改 | 能在 AI 生成结果基础上独立改动 | 普通代码、脚本、配置 |
| D4 | Debug / 能定位问题 | 出问题时知道从哪里开始查 | 工程系统、高风险代码、生产问题 |
| D5 | Design / 能独立设计 | 能比较替代方案，解释取舍，并独立设计类似系统 | 架构、核心业务、Agent 系统、安全、平台化工具 |

### 6.4.1 默认掌握颗粒度建议

| 用户定位 | 默认掌握颗粒度 |
|---|---|
| Software Engineer | D4 Debug |
| Full-stack Builder | D3 Modify |
| AI Agent Builder | D5 Design |
| Product Builder | D2 Explain / D3 Modify |
| Research Builder | D2 Explain / D5 Evaluate |
| Creative Builder | D2 Explain / D3 Iterate |

### 6.4.2 按领域配置，而不是全局固定

同一用户在不同领域需要不同深度。

例如：

```json
{
  "mastery_profile": {
    "automotive_embedded": "D5",
    "ai_agent_tooling": "D5",
    "frontend": "D3",
    "product_design": "D3",
    "visual_design": "D2"
  }
}
```

不要只有一个全局字段：

```json
{
  "depth": "deep"
}
```

那会过于粗糙。

---

## 6.5 自动推断：从项目和 Session 行为校准用户定位

冷启动问卷只能给初值，真实定位要靠行为推断。

### 6.5.1 项目信号

| 信号 | 推断 |
|---|---|
| `package.json` + `frontend/backend` | Full-stack Builder |
| `src/components`、Tailwind、Figma 链接 | Frontend / Product Builder |
| `mcp.json`、`AGENTS.md`、`.claude/`、hooks | AI Agent Builder |
| `pytest`、`tests/`、CI config | Software Engineer |
| `docs/prd`、`requirements`、`user-story` | Product Builder |
| `notebooks`、`papers`、`references` | Research Builder |
| `game`、`unity`、`godot`、`assets` | Game / Creative Builder |

### 6.5.2 Prompt 信号

| 用户常用表达 | 推断 |
|---|---|
| “帮我实现”“报错了”“怎么 debug” | Software Engineer |
| “这个架构是否合理”“模块怎么拆” | Engineer / Agent Builder |
| “MVP 怎么做”“有没有搞头” | Product Builder / Indie Builder |
| “用户路径”“冷启动”“留存” | Product Builder |
| “Hook / Skill / MCP / Agent” | AI Agent Builder |
| “竞品调研”“市场空间” | Research / Product Builder |
| “风格”“叙事”“意象” | Creative Builder |

### 6.5.3 Tool Call / Diff 信号

| 行为 | 推断 |
|---|---|
| AI 大量修改代码 | Software / Full-stack |
| AI 生成 PRD / Markdown / Spec | Product / Research |
| AI 配置 hooks / MCP / CLI | AI Agent Builder |
| AI 频繁跑 test / lint / build | Engineer |
| AI 修改 Docker / deploy / DB schema | Full-stack / DevOps |
| AI 生成设计图提示词 / story bible | Creative Builder |

---

## 6.6 冷启动校准任务

冷启动可以用一个“最近任务校准”替代复杂测验。

示例：

```text
请选择你最近最常用 AI 完成的一类任务：

A. 修一个 bug
B. 实现一个功能
C. 设计一个架构
D. 写一份 PRD
E. 做一个调研
F. 搭一个 Agent / MCP 工具
```

如果用户选择 C，系统继续问：

```text
AI 帮你设计了一个 MCP + Hook + Skill 的工具系统。
你希望自己掌握到什么程度？

A. 能复述整体结构
B. 能解释每层职责
C. 能自己改一个模块
D. 出问题能 debug
E. 能独立重做这个架构
```

该校准任务可直接生成 `mastery_depth` 和 `debt_priority`。

---

## 6.7 初始 AI Debt Profile 数据结构

冷启动结束后生成：

```json
{
  "profile_version": "0.1",
  "primary_role": "AI Agent Builder",
  "secondary_roles": ["Software Engineer", "Product Builder"],
  "default_work_mode": "L1",
  "default_mastery_depth": "D4",
  "domain_depth": {
    "ai_agent_tooling": "D5",
    "software_engineering": "D4",
    "product_design": "D3",
    "frontend": "D3"
  },
  "debt_priority": {
    "architecture_decision": 1.4,
    "debug_root_cause": 1.3,
    "framework_usage": 1.1,
    "visual_polish": 0.6
  },
  "interruption_policy": {
    "during_build": "silent",
    "idle_review": true,
    "high_risk_nudge": true,
    "auto_l2": false
  }
}
```

---

## 6.8 后续自适应校准

AI Debt 应基于后续真实使用持续更新画像。

### 6.8.1 校准规则示例

| 观察到的行为 | 系统调整 |
|---|---|
| 用户多次跳过 L2/L3 | 降低默认学习提示强度 |
| 用户经常点开架构类债务 | 提高 architecture_decision 权重 |
| 用户总能通过某类 Grasp Check | 降低该领域债务优先级 |
| 用户反复在某类债务上失败 | 提升为 L4 学习路径候选 |
| 用户频繁要求“详细解释” | 提高 default_mastery_depth |
| 用户经常选择“稍后”但周末处理 | 增强 weekly review 权重 |
| 用户在某领域只看 L1 | 将该领域深度目标降为 D2/D3 |

### 6.8.2 三次 Session 后的校准提示

系统在收集若干次真实 Build Trace 后，可给出温和建议：

```text
AI Debt 根据最近 3 次 Build 观察到：
你主要在做 AI Agent / 系统架构类任务；
建议把 Agent Tooling 的掌握目标从 D3 调整为 D5。

[接受] [保持原设置]
```

---

## 6.9 MVP 冷启动范围

MVP 不做复杂画像系统，只做 4 步：

```text
1. 角色选择：你主要是哪类 Builder？
2. 掌握目标：你希望 AI 生成内容掌握到哪级？
3. 打扰偏好：默认静默还是 30 秒速记？
4. 债务优先级：最怕哪类东西没理解？
```

MVP 的冷启动输出：

```json
{
  "primary_role": "AI Agent Builder",
  "default_work_mode": "L1",
  "default_mastery_depth": "D4",
  "debt_priority_focus": ["architecture_decision", "debug_root_cause"],
  "interruption_policy": "idle_review_only"
}
```

后续版本再加入：

```text
- 项目信号自动识别
- Prompt 信号持续学习
- Tool Call / Diff 行为校准
- 按领域 mastery profile
- 三次 Session 后自适应建议
```

---

# 7. 总体架构

## 6.1 架构总览

```text
┌──────────────────────────────────────────────┐
│ Layer 1: Client Integration                   │
│ Claude Code / Codex / Cursor / CLI / Web UI   │
└──────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│ Layer 2: Trigger Layer                        │
│ Hooks / Commands / Manual Invocation          │
│ SessionEnd / Stop / PostToolUse / /ai-debt    │
└──────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│ Layer 3: Build Trace Layer                    │
│ Transcript / Diff / Tool Calls / Errors       │
└──────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│ Layer 4: Cognitive Debt Engine                │
│ Delegation Audit / Debt Mark / Debt Scoring   │
│ Intent Capture / Grasp Check Generation       │
└──────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│ Layer 5: MCP Capability Layer                 │
│ Tools / Resources / Prompts                   │
└──────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│ Layer 6: State Layer                          │
│ Debt Ledger / Learning Inbox / User Profile   │
│ Session Store / Concept Cluster               │
└──────────────────────────────────────────────┘
```

---

## 6.2 核心闭环

```text
AI 替你做了什么
        ↓
你是否理解
        ↓
不理解则记债
        ↓
有空再学
        ↓
通过 Grasp Check
        ↓
销账
```

---


## 6.3 Journal-first + Idle-settlement 触发模型

实际使用 Claude Code / Codex / Cursor 等终端 Agent 时，用户不一定会主动执行 End Session。更常见的行为包括：

```text
Ctrl+C
直接 kill terminal
关闭 pane / tab
电脑休眠
切去别的任务
几小时后 resume
```

因此 AI Debt 不应采用 `SessionEnd-first` 设计，而应采用：

```text
Journal-first + Stop 轻分析 + Idle Timeout 深分析 + Next-start Recovery
```

### 6.3.1 触发分层

| 层级 | 触发点 | 行为 | 是否打扰用户 |
|---|---|---|---|
| 实时记录 | UserPromptSubmit / PostToolUse / Stop | 持续写入 Build Journal | 否 |
| 轻度分析 | Stop | 增量更新 debt candidates | 否 |
| 逻辑结算 | Idle Timeout | 汇总 journal，执行深度分析，生成 Pending Review | 只生成轻提示 |
| 兜底结算 | SessionEnd | 标记 session closed，尽量触发 pending review | 不依赖 |
| 恢复结算 | SessionStart / 下次启动 | 恢复 orphaned journal，补生成 pending review | 可提示 |

### 6.3.2 Stop 阶段：记录 + 轻分析

Stop 阶段不做教学，不弹学习内容，只做低成本记录和轻量增量分析：

```text
记录本轮 assistant response
记录 transcript path
记录本轮 tool call summary
记录 changed files / git diff hash
抽取候选认知债关键词
更新 session activity timestamp
写入 events.jsonl / debt_candidates.json
```

Stop 阶段禁止做：

```text
完整复盘
L3 深度解释
多 Agent 深分析
强制 Grasp Check
自动弹窗打断
```

### 6.3.3 Idle Timeout 阶段：深分析 + Pending Review

Idle Timeout 更符合真实工作流中的“逻辑结束点”。当一段时间无用户输入、工具调用或模型响应后，系统认为当前 Build Trace 进入冷却期，可以做深度分析。

建议 MVP 阈值：

```text
15 分钟无活动：标记 idle
30 分钟无活动：执行深度分析并生成 Pending Review
```

Idle Timeout 阶段执行：

```text
汇总当前 session journal
读取 transcript / diff / terminal log
识别 AI delegation points
提取 cognitive debt items
计算 P0/P1/P2
合并重复债务
生成 L1 30 秒速记
写入 Learning Inbox
```

注意：Idle Timeout 不是自动展开 L2/L3，而是自动完成分析并生成 L1 级别的 Pending Review。

### 6.3.4 Recovery 阶段：terminal 被 kill 后不丢债

如果 terminal 被 kill 或 SessionEnd 未触发，AI Debt 应在下次启动时根据本地 journal 恢复未结算 session：

```text
发现 events.jsonl 存在但未 reviewed
  ↓
恢复 session summary
  ↓
重新执行或补齐深度分析
  ↓
生成 pending review
```

用户看到的是：

```text
上次 AI Build 没有正常结束，我从 journal 里恢复了 2 个 pending review。
[查看 30 秒速记] [稍后]
```

### 6.3.5 新状态机

```text
active
  ↓ Stop / ToolUse
recording
  ↓ no activity for 15min
idle
  ↓ no activity for 30min
analyzing
  ↓ analysis done
pending_review
  ↓ user opens L1/L2/L3
reviewed
```

异常路径：

```text
active / recording
  ↓ terminal killed
orphaned
  ↓ next startup
recovering
  ↓ rebuild from journal
pending_review
```

---

# 8. 核心模块设计

## 7.1 Build Trace

### 职责

在 AI Build 过程中捕获足够上下文，但不打断用户。

### 输入来源

```text
conversation transcript
user prompts
AI responses
git diff
changed files
tool calls
terminal history
test output
error logs
commit metadata
project metadata
```

### 输出

```json
{
  "session_id": "session_20260619_001",
  "source": "claude_code",
  "project": "ai-debt",
  "transcript_path": "./sessions/session_001/transcript.md",
  "diff_path": "./sessions/session_001/diff.patch",
  "tool_calls_path": "./sessions/session_001/tool_calls.json",
  "terminal_log_path": "./sessions/session_001/terminal.log",
  "mode": "work"
}
```

---

## 7.2 AI Delegation Audit

### 职责

识别本次 Session 中 AI 替用户完成了哪些关键推理和判断。

### 典型代劳点

| 类型 | 示例 |
|---|---|
| 架构判断 | AI 判断 MCP 应作为能力暴露层，而不是触发层 |
| 调试推理 | AI 根据日志定位根因 |
| 代码实现 | AI 生成关键错误处理或状态机逻辑 |
| 工具决策 | AI 选择并执行 shell command |
| 方案取舍 | AI 比较替代方案并给出推荐 |
| 安全判断 | AI 修改认证、权限、数据删除相关路径 |
| 测试设计 | AI 决定测试断言覆盖哪些边界 |

### 输出

```json
{
  "delegation_points": [
    {
      "type": "architecture_decision",
      "description": "AI 判断 Hook 负责触发，MCP 负责能力暴露。",
      "user_followup": false,
      "risk_if_not_understood": "后续可能把触发、交互和状态管理塞进 MCP。",
      "related_concepts": ["Hook", "MCP", "Skill"],
      "risk_level": "high"
    }
  ]
}
```

---

## 7.3 Cognitive Debt Mark

### 职责

将 AI 代劳点转化为候选认知债。

### 判断规则

```text
如果 AI 完成了关键推理，且用户没有追问/验证/复述：
    生成认知债候选

如果 AI 修改了高风险路径，且用户没有确认失败分支：
    生成高优先级认知债

如果某概念在多次 Session 中重复出现，且状态仍未掌握：
    提升优先级
```

### 输出

```json
{
  "debt_candidates": [
    {
      "type": "cognitive_debt",
      "concept": "Hook / Skill / MCP 边界",
      "source_session": "session_20260619_001",
      "why_it_matters": "AI 替用户完成了工具架构分层判断。",
      "evidence": [
        "用户询问是否整个服务都设计成 MCP",
        "AI 给出 Hook / Skill / MCP 职责划分",
        "用户未进行反向解释或方案比较"
      ],
      "priority": "P1",
      "status": "unverified"
    }
  ]
}
```

---

## 7.4 Intent Debt Capture

### 职责

捕获设计意图、决策理由和被放弃的替代方案。

认知债经常来自“只知道结果，不知道为什么”。因此每次 AI 给出方案时，系统应尽量记录：

```text
为什么选这个方案？
为什么不用另一个方案？
这个设计依赖什么假设？
什么情况下这个方案会失效？
未来维护者需要知道什么？
```

### 输出

```json
{
  "intent_items": [
    {
      "decision": "MCP 作为能力暴露层，而不是触发层。",
      "rationale": "MCP 适合暴露 tools/resources/prompts，不适合作为生命周期触发器。",
      "rejected_alternatives": [
        "纯 MCP Server 承担所有职责",
        "只用 Skill 不做 Hook"
      ],
      "assumptions": [
        "Claude Code / Codex 支持 Hook 或类似生命周期事件",
        "用户希望 Local-first"
      ]
    }
  ]
}
```

---

## 7.5 Technical Debt Signals

### 职责

技术债信号只服务于认知债判断，不作为核心产品输出。

### 信号示例

| 信号 | 可能触发的认知债 |
|---|---|
| AI 修改关键路径 | 用户是否理解关键路径失败模式 |
| 复杂度上升 | 用户是否理解新控制流 |
| 缺少测试 | 用户是否知道需要验证什么 |
| 错误处理被 AI 生成 | 用户是否理解异常分支 |
| 认证/支付/数据删除路径变化 | 用户是否理解安全后果 |
| 并发/状态机逻辑变化 | 用户是否理解时序和恢复策略 |
| 数据迁移脚本变化 | 用户是否理解回滚和破坏性影响 |

---

## 7.6 Session Review

### 职责

Idle Timeout / Pending Review 后进行认知债筛选，而不是强制教学。

### 默认输出

```text
本次 Build 记录到 3 个认知债。

P1：Hook / Skill / MCP 边界
P1：AI 代劳的架构分层判断
P2：MCP Tool 粒度设计

[跳过并记录] [30 秒速记] [学一个重点] [深度复盘]
```

---

## 7.7 Learning Inbox

### 职责

把用户没时间学习的认知债暂存起来，并在合适时间推荐偿还。

### 推荐逻辑

优先推荐：

```text
高风险
重复出现
当前项目强相关
用户目标强相关
影响后续架构判断
用户自评未掌握或未验证
```

---

## 7.8 Grasp Check

### 职责

判断用户是否真正掌握某个债务，而不是只看过解释。

### 检查层级

| 层级 | 检查方式 |
|---|---|
| Recall | 能否复述概念 |
| Trace | 能否追踪流程 |
| Debug | 出错时是否知道从哪里查 |
| Modify | 能否修改实现 |
| Transfer | 能否迁移到新场景 |
| Manual | 能否在 AI 不在时复现关键逻辑 |

### 示例问题

```text
请不用 AI，用一句话解释：
为什么 Hook 适合作为 SessionEnd 触发器，而 MCP 不适合？
```

---

## 7.9 Debt Ledger

### 职责

长期记录认知债状态、证据、优先级、重复次数和偿还情况。

### 数据结构

```json
{
  "id": "debt_20260619_001",
  "type": "cognitive_debt",
  "concept": "Hook / Skill / MCP 边界",
  "domain": "AI Agent Tooling",
  "source_session": "session_20260619_001",
  "why_it_matters": "用户在 AI Debt 架构设计中需要区分触发层、交互层和能力层。",
  "evidence": [
    "用户询问是否整个服务都设计成 MCP",
    "AI 给出职责划分",
    "用户未进行反向解释"
  ],
  "priority": "P1",
  "risk_level": "high",
  "depth_target": "can_design_independently",
  "status": "unverified",
  "seen_count": 3,
  "next_review": "2026-06-22",
  "resolved_at": null
}
```

---

# 9. 交互设计

## 8.1 构建中：静默记录为主

默认行为：

```text
不弹窗
不解释
不要求微测
不阻塞 AI Build
```

只在后台记录：

```text
AI 关键判断
Diff 高风险变化
用户是否追问
用户是否验证
潜在认知债
```

---

## 8.2 构建中：轻量提示的触发条件

只有以下情况允许提示：

1. 高风险路径：认证、支付、数据删除、DB migration、安全、并发状态机、生产配置。
2. 同一认知债重复出现多次。
3. 用户主动开启 Learn Mode。
4. AI 代劳点明显会影响后续架构判断。

提示也必须极短：

```text
已记录一个潜在认知债：AI 替你完成了状态机恢复策略判断。
```

用户点击后才展开。

---

## 8.3 Session 结束：四按钮交互

```text
本次 Build 记录到 3 个认知债。

[跳过并记录] [30 秒速记] [学一个重点] [深度复盘]
```

对应行为：

| 选项 | 行为 |
|---|---|
| 跳过并记录 | 只写入 Ledger，不展示内容 |
| 30 秒速记 | 展示概念名、来源、风险 |
| 学一个重点 | 展开最重要的一条认知债 |
| 深度复盘 | 生成完整 Session Review |

---

## 8.4 之后学习：命令入口

```bash
ai-debt review
ai-debt inbox
ai-debt learn-one
ai-debt check <debt-id>
ai-debt weekly
ai-debt ledger
```

---


## 8.5 L0-L4 入口设计

L0/L1 是系统默认行为，L2/L3/L4 不应依赖“设置页里切模式”，而应围绕具体认知债自然展开。

| 入口 | 默认模式 | 可进入模式 | 适用场景 |
|---|---|---|---|
| Pending Review / Session Review 卡片 | L1 | L2/L3/L4 | Idle Timeout 后或用户主动 review |
| Learning Inbox | L1 | L2/L3/L4 | 用户有空偿还债务 |
| 单个 Debt 详情页 | L1 | L2/L3/Grasp Check | 处理某条具体认知债 |
| CLI / Command | 用户指定 | L0-L4 | 开发者主动调用 |
| Terminal Companion 气泡 | L0/L1 | L2 | 低打扰提示 |
| Weekly Review | L1 | L3/L4 | 重复债务聚类后系统学习 |

关键原则：

```text
用户不是选择“我要进入 L3 模式”，
而是看到一个认知债后选择“我要深入理解这个债”。
```

## 8.6 Terminal-embedded Companion UI

AI Debt 可以保留 Companion / Buddy 形态，但 **MVP 优先采用终端嵌入式 Companion，而不是浮动桌宠**。

产品本体仍是 AI Debt Core：Build Journal、Cognitive Debt Analyzer、Debt Ledger、Learning Inbox、Grasp Check。Terminal Companion 只是低打扰前台入口，用来在 Stop / Idle Timeout / Pending Review / 重复认知债出现时，在用户本来工作的终端上下文里给出极短提示。

定位：

```text
AI Debt Core = 认知债分析与长期账本
Terminal Companion = 嵌入终端的低打扰提示层
Desktop Pet = 后续可选增强，不进入 MVP 主线
```

### 8.6.1 为什么优先终端嵌入，而不是浮动桌宠

claude-minipet 的形态更接近 AI Debt 需要的 MVP：它是一只住在 Claude Code 终端里的虚拟宠物，通过 Claude Code hooks 和守护进程运行，在终端底部显示实时气泡，并根据 coding 活动变化状态。它的 README 明确写到需要 Node.js 和 Claude Code，安装后会配置 Claude Code hooks 并启动守护进程；它的气泡示例也是嵌入终端底部的 TUI 文本框。

Petdex / OpenPets 代表的是另一类方向：更完整的桌面宠物 / Companion 平台。Petdex 面向 Codex、Claude Code、OpenCode、Gemini CLI 等 coding agents，并包含宠物图库、CLI 安装器和桌面应用；OpenPets 是 desktop companion platform，包含 animated pets、Plugin SDK、官方插件和 optional local coding-agent integrations。

两者对 AI Debt 的启发不同：

```text
claude-minipet 启发：终端内气泡 / TUI Companion，更适合 MVP。
Petdex / OpenPets 启发：跨工具、桌面浮层、生态化 Companion，更适合后续 Adapter。
```

### 8.6.2 实现复杂度对比

| 方案 | 实现复杂度 | 多工具能力 | 工作流贴合度 | MVP 适合度 |
|---|---:|---:|---:|---:|
| 纯 CLI 提示 | 最低 | 高 | 中 | 可作为 v0.1 fallback |
| Terminal Companion / TUI 气泡 | 低-中 | 需要 Adapter | 高 | **最适合** |
| IDE 侧边栏 | 中 | 中 | 中 | 后续可做 |
| Desktop Floating Pet | 中高 | 可做但复杂 | 中 | 后续可选 |
| Companion Platform / 插件生态 | 高 | 高 | 中 | 不适合 MVP |

浮动桌宠复杂度主要来自：

```text
桌面窗口置顶 / 透明背景 / 拖拽 / 多显示器
macOS / Windows / Linux 差异
托盘、自动启动、权限、代码签名
动画资源系统
MCP / Hook / WebSocket / local server 通信
避免遮挡 IDE / Terminal / Browser
安装、升级、卸载体验
```

终端 Companion 的复杂度主要来自：

```text
在合适时机输出短提示
不破坏 Claude Code / Codex 主输出
管理 Pending Review 状态
支持简单交互命令
适配不同 terminal 宽度
避免在用户输入中途插入内容
```

因此，AI Debt 的 MVP 不应先做浮动桌宠，而应先做终端嵌入式 Companion。

### 8.6.3 多工具支持策略

claude-minipet 当前更像 Claude Code 专用形态：它依赖 Claude Code hooks 和 Claude Code TUI，因此不天然支持 Codex / OpenCode / Cursor。

AI Debt 应该借鉴它的 UI 形态，但不能把核心能力绑定到 Claude Code。底层需要从一开始抽象成事件模型和 Adapter：

```text
ai-debt-core
├── Build Journal
├── Idle Settlement
├── Cognitive Debt Analyzer
├── Debt Ledger
└── Review Generator

ai-debt-adapters
├── claude-code adapter
├── codex adapter
├── opencode adapter
├── cursor / generic mcp adapter
└── transcript import adapter

ai-debt-terminal-companion
├── TUI bubble
├── status line
├── pending review card
└── command shortcuts
```

统一事件模型示例：

```ts
type AgentEvent =
  | { type: "user_prompt"; source: "claude" | "codex" | "opencode" | "cursor" }
  | { type: "assistant_stop"; source: string; transcriptPath?: string }
  | { type: "tool_use"; source: string; tool: string; files?: string[] }
  | { type: "diff_changed"; files: string[] }
  | { type: "idle_timeout"; sessionId: string }
  | { type: "terminal_recovered"; sessionId: string }
```

关键原则：

```text
UI 可以先适配 Claude Code TUI；
Core 必须保持工具无关；
多工具差异在 Adapter 层消化。
```

### 8.6.4 Terminal Companion 适合承载的模式

| AI Debt 模式 | Terminal Companion 是否适合 | 表现形式 |
|---|---:|---|
| L0 静默记录 | 适合 | 状态行 / 极短提示，不弹正文 |
| L1 30 秒速记 | 非常适合 | Idle 后气泡提示“记录到 3 个认知债” |
| L2 3 分钟轻学 | 适合 | 用户点气泡或命令进入一个重点解释 |
| L3 深度复盘 | 不适合作为主界面 | Companion 只做入口，正文进入 Markdown / CLI / Web |
| L4 系统学习路径 | 不适合作为主界面 | Companion 只提示“本周可生成学习路径” |

### 8.6.5 推荐交互样式

Stop 后：只显示极轻状态，不教学。

```text
╭─ AI Debt ─────────────────────╮
│ recording · 2 candidate debts │
╰───────────────────────────────╯
```

Idle Timeout 后：显示 L1 Pending Review。

```text
╭─ AI Debt ─────────────────────────────────────╮
│ 我帮你记下了 3 个认知债。                    │
│ Top: AI 替你做了 Hook / MCP / Skill 边界判断 │
│                                                │
│ [1] 30 秒速记  [2] 学一个重点  [3] 稍后       │
╰──────────────────────────────────────────────╯
```

用户进入 L2：终端只承载短解释和一个检查问题。

```text
╭─ AI Debt · Learn One ─────────────────────────╮
│ 认知债：Hook / MCP / Skill 边界               │
│                                                │
│ 一句话：Hook 管触发，Skill 管协作，MCP 管能力。│
│                                                │
│ 检查：Idle Timeout 后自动生成 review，主要    │
│ 应该靠 Hook 还是 MCP？                         │
╰──────────────────────────────────────────────╯
```

L3/L4 不要塞进气泡，应生成 Markdown / Web / CLI 长文本。

### 8.6.6 Terminal Companion 的架构边界

```text
AI Debt Core
├── Build Journal
├── Cognitive Debt Analyzer
├── Debt Ledger
├── Learning Inbox
├── Grasp Check
└── Review Generator

AI Debt Terminal Companion
├── Status Line
├── Idle Review Bubble
├── Debt Count Badge
├── High-risk Debt Nudge
├── Learn-one Entry
└── Command Shortcuts

AI Debt Desktop Companion Adapter（后续可选）
├── Petdex Adapter
├── OpenPets Adapter
└── Custom Floating Pet Adapter
```

Terminal Companion 气泡不能成为唯一状态来源。所有结构化状态必须写入 AI Debt Core 的 Ledger / Journal / Inbox。

### 8.6.7 提示频率规则

默认规则：

```text
Stop 阶段只更新状态，不弹学习内容
Idle 后最多弹一次
同一 debt 不重复弹
P2 不弹
P0/P1 才提示
用户选择“稍后”后当天不再提示
用户正在输入时不插入气泡
L3/L4 只给入口，不在终端气泡内展开
```


# 10. L0-L4 学习模式系统

## 9.1 模式定义

AI Debt 的学习模式统一采用 L0-L4，避免 Capture / Brief / Focus / Learn / Review 等复杂命名。

| 模式 | 名称 | 核心作用 | 典型入口 |
|---|---|---|---|
| L0 | 静默记录 | 干中记，只捕获和标记，不提示 | 默认模式、Stop/PostToolUse |
| L1 | 30 秒速记 | 查看本次最重要的 1-3 个认知债 | Pending Review、Terminal Companion 气泡、`ai-debt review` |
| L2 | 3 分钟轻学 | 围绕一个认知债做最小解释和一个检查问题 | “学一个重点”、`ai-debt learn-one` |
| L3 | 深度复盘 | 完整解释概念、AI 代劳点、风险、替代方案、Grasp Check | Debt 详情页、`ai-debt deep <debt-id>` |
| L4 | 系统学习路径 | 将反复出现的债务聚合成学习路线 | Weekly Review、重复 debt cluster |

## 9.2 默认策略

```text
L0 是默认工作模式。
L1 是 Idle Timeout / Pending Review 的默认输出。
L2 是最常用的学习入口。
L3 只在用户主动要求时进入。
L4 用于周复盘 / 月复盘 / 某类债务反复出现时。
```

## 9.3 模式切换原则

用户不需要在设置页里频繁切模式。大多数情况下，模式由“债务对象 + 用户动作”决定：

```text
看到 Pending Review → L1
点击“学一个重点” → L2
点击“深度复盘” → L3
某类认知债重复出现 → L4
不点击任何东西 → 维持 L0，债务进入 Inbox
```

## 9.4 与产品公式的对应关系

```text
默认干中记：L0
按需干中学：L2，少量 L1 inline hint
事后集中学：L3 / L4
长期偿还债：Learning Inbox + Debt Ledger + Grasp Check
```

---

# 11. MCP / Hook / Skill 边界

## 10.1 职责分工

| 组件 | 职责 | 不负责 |
|---|---|---|
| Hook | 捕获生命周期事件、采集 Build Trace、触发 Stop 轻分析与 Idle 结算 | 复杂教学、长期状态 |
| MCP | 暴露分析、查询、账本更新能力 | 生命周期触发、UI |
| Skill | 定义复盘方法、Grasp Check、解释风格 | 数据库存储、跨客户端同步 |
| CLI / UI | 用户选择、查看 Inbox、执行 Check | 核心分析算法 |
| State Layer | Ledger、Profile、Session Store、Concept Cluster | 客户端绑定 |

---

## 10.2 MCP Tools

```text
ai_debt.analyze_session
ai_debt.mark_cognitive_debt
ai_debt.generate_review
ai_debt.get_inbox
ai_debt.run_grasp_check
ai_debt.update_ledger
ai_debt.resolve_debt
ai_debt.get_pending_review
ai_debt.emit_companion_event
```

### ai_debt.analyze_session

输入：

```json
{
  "session_id": "session_001",
  "transcript": "...",
  "git_diff": "...",
  "tool_calls": "...",
  "terminal_history": "...",
  "errors": "..."
}
```

输出：

```json
{
  "task_summary": "...",
  "delegation_points": [],
  "cognitive_debt_candidates": [],
  "intent_items": [],
  "technical_debt_signals": []
}
```

### ai_debt.run_grasp_check

输入：

```json
{
  "debt_id": "debt_001",
  "user_answer": "...",
  "target_depth": "can_debug"
}
```

输出：

```json
{
  "understanding_level": "unknown | shallow | partial | solid",
  "feedback": "...",
  "resolved": false
}
```

---

# 12. 数据存储设计

## 11.1 Local-first 目录结构

```text
~/.ai-debt/
├── config.yaml
├── ai_debt.db
├── sessions/
│   └── session_20260619_001/
│       ├── transcript.md
│       ├── diff.patch
│       ├── tool_calls.json
│       ├── terminal.log
│       └── analysis.json
├── ledger/
│   ├── cognitive_debts.json
│   ├── concept_clusters.json
│   └── resolved_debts.json
├── exports/
│   ├── markdown/
│   ├── obsidian/
│   └── anki/
└── logs/
```

---

## 11.2 核心表

### sessions

| 字段 | 类型 | 说明 |
|---|---|---|
| id | text | Session ID |
| source | text | Claude Code / Codex / Cursor |
| project | text | 项目名 |
| started_at | datetime | 开始时间 |
| ended_at | datetime | 结束时间 |
| summary | text | 摘要 |
| mode | text | 当前学习模式 |

### cognitive_debts

| 字段 | 类型 | 说明 |
|---|---|---|
| id | text | 债务 ID |
| concept | text | 概念名 |
| domain | text | 领域 |
| source_session | text | 来源 Session |
| why_it_matters | text | 为什么重要 |
| evidence | json | 证据 |
| priority | text | P0/P1/P2 |
| status | text | unverified / partial / solid / resolved |
| seen_count | integer | 重复出现次数 |
| next_review | datetime | 下次复盘时间 |

### delegation_points

| 字段 | 类型 | 说明 |
|---|---|---|
| id | text | 代劳点 ID |
| session_id | text | 来源 Session |
| type | text | 架构判断 / 调试推理 / 代码实现等 |
| description | text | 描述 |
| related_debt_id | text | 关联认知债 |

### grasp_checks

| 字段 | 类型 | 说明 |
|---|---|---|
| id | text | 检查 ID |
| debt_id | text | 关联债务 |
| question | text | 问题 |
| user_answer | text | 用户回答 |
| result | text | 结果 |
| created_at | datetime | 创建时间 |

---

# 13. 竞品与相邻项目调研（v3 更新）

## 12.1 总体结论

GitHub 上已经出现多个 cognitive debt / AI debt / comprehension gate 相关项目。v2 的判断需要修正：

```text
AI Debt 不是概念空白。
AI-generated code debt、cognitive debt scoring、quiz plugin、session capture 都已有相邻项目。
```

但仍未看到一个完整覆盖以下链路的成熟项目：

```text
AI Build Session 捕获
→ AI 代劳点审计
→ 认知债标记
→ 事后分级复盘
→ Learning Inbox
→ Grasp Check
→ 长期 Ledger
→ MCP + Hook + Skill 一体化
```

---

## 12.2 重点项目总览

| 项目 | 类型 | 与 AI Debt 的关系 | 可借鉴点 |
|---|---|---|---|
| `aditya-rajesh2006/AIDebtLens` | Repo/File 级 AI Debt Lens | 概念重合度高，形态不同 | AI likelihood、technical/cognitive debt scoring、dashboard、commit trends、propagation graph |
| `ryannadel/cognitive-coverage` | 理解覆盖率系统 | 长期理解管理接近 | concept status、coverage manifest、MCP |
| `jobrien874/why-plugin` | Claude quiz plugin | 微测接近 | WHAT/HOW/WHY quiz、不强制阻塞 |
| `kesslernity/cognitive-debt-prevention-kit` | 团队流程模板 | 治理相邻 | checklist、PR gate、MEMORY.md |
| `aptratcn/cognitive-debt-guard` | Skill / guardrail | 规则相邻 | comprehension gate、AI-free zones |
| `sebamar88/ai-debt-scanner` | AI 技术债 scanner | 名称/代码债接近 | diff scan、severity、pre-commit |
| `gammons/ai-session` | Claude transcript capture | Session capture 参考 | transcript + commit/PR link |
| `hamelsmu/claude-review-loop` | Claude + Codex review loop | Hook workflow 参考 | Stop hook、phase lifecycle |

---

## 12.3 `aditya-rajesh2006/AIDebtLens`

### 项目定位

AIDebtLens 是一个 explainable static analysis tool，用来检测和沟通 AI-generated code 引入的 technical debt。它基于 React + Supabase，支持 GitHub 仓库、上传文件和粘贴代码分析，并计算 AI-generated code risk、technical debt、cognitive debt。

仓库地址：

```text
https://github.com/aditya-rajesh2006/AIDebtLens
```

### 当前能力

AIDebtLens 当前支持：

- Public GitHub repository analysis
- Single-file upload analysis
- Pasted code analysis
- Technical debt / cognitive debt / AI-likelihood scoring
- File-level metric breakdown
- Commit timeline analysis
- Propagation graph / hotspot views
- Refactor recommendations
- Downloadable reports
- Auth-backed history
- In-app chatbot
- Human cognitive model / developer cognitive simulation views

### 与 AI Debt 的重合点

| 维度 | AIDebtLens | AI Debt |
|---|---|---|
| AI Debt 概念 | 高度相关 | 核心命名 |
| Cognitive Debt | 用作代码认知负担评分 | 用作用户理解债核心对象 |
| Technical Debt | 主分析对象之一 | 只作为辅助信号 |
| AI-generated code | 重点识别 | 可作为证据，不是主线 |
| Dashboard | 核心形态 | 后续可选，不是 MVP |
| 历史记录 | Supabase analysis history | Local-first Debt Ledger |

### 最大差异

AIDebtLens 问的是：

```text
这段代码 / 这个仓库里有多少 AI 诱发的技术债和认知负担？
```

AI Debt 问的是：

```text
这次 AI Build Session 之后，你本人欠下了哪些认知债？
```

一句话差异化：

```text
AIDebtLens 看代码里留下了什么债。
AI Debt 看你在 AI Build 过程中欠下了什么理解。
```

### 对 AI Debt 的影响

AIDebtLens 已经覆盖了较完整的 repo/file-level AI debt dashboard 方向。因此 AI Debt 不应再把以下能力作为主卖点：

- AI-generated code likelihood detection
- Repo-level technical debt scoring
- Code complexity / nesting / duplication / naming heuristics
- Debt heatmap
- Propagation graph
- Commit timeline debt trend
- Refactor recommendation
- Dashboard-first repo analysis

AI Debt 应明确收窄为：

```text
Session-level cognitive debt tracker for AI-assisted builders.
```

---

## 12.4 `ryannadel/cognitive-coverage`

项目定位：

```text
Like test coverage, but for understanding.
```

它关注项目级理解覆盖率，生成 learning guide、coverage manifest、dashboard，并支持 optional MCP server。

与 AI Debt 差异：

| 维度 | Cognitive Coverage | AI Debt |
|---|---|---|
| 核心对象 | 项目 / 代码库 / 知识库 | AI Build Session |
| 核心问题 | 系统有哪些概念未理解 | AI 替你做了什么判断 |
| 输出 | coverage dashboard | cognitive debt ledger + inbox |
| 触发 | 主动生成 | Hook / SessionEnd 自动捕获 |

借鉴点：concept status、coverage manifest、MCP tool 设计。

---

## 12.5 `jobrien874/why-plugin`

项目定位：

```text
Combat cognitive debt from Claude AI-assisted development.
```

它通过 quiz 检查用户是否理解 Claude 生成的代码，提出 WHAT / HOW / WHY 三层问题。

与 AI Debt 差异：

| 维度 | WHY Plugin | AI Debt |
|---|---|---|
| 核心功能 | Quiz | Ledger + Review + Inbox + Check |
| 时间尺度 | 当前代码块 / 当前 Session | 长期认知债管理 |
| 触发 | 用户或 auto quiz | Hook + SessionEnd + 手动 |

借鉴点：WHAT / HOW / WHY 可作为 Grasp Check 的问题模板。

---

## 12.6 其他项目简评

### cognitive-debt-prevention-kit

偏团队流程模板，适合借鉴 checklist、PR gate、MEMORY.md，但不适合作为 AI Debt 主形态。

### cognitive-debt-guard

偏 skill / guardrail，适合借鉴 comprehension gate、AI-free zones、高风险路径规则。

### ai-debt-scanner

偏 AI-generated technical debt scanner，适合借鉴 diff scan、severity scoring、pre-commit hook，但其核心对象是代码技术债，不是用户认知债。

### ai-session

非常适合作为 Build Trace / Session Capture Layer 参考，尤其是 transcript 本地存储、commit/PR 双向关联、不污染代码仓库。

### claude-review-loop

适合借鉴 Stop hook、phase lifecycle、review markdown output。AI Debt 可以采用类似：

```text
Task phase: AI Build
Debt phase: AI Debt Review
Learning phase: 用户选择 silent / brief / deep
```

---

# 14. 差异化定位

经过 v3 收敛，AI Debt 的差异化定位是：

```text
AI Debt is not a repo-level static analysis dashboard.
AI Debt is not a technical debt scanner.
AI Debt is not a quiz plugin only.
AI Debt is a session-level cognitive debt tracker for AI-assisted builders.
```

中文：

```text
AI Debt 不是仓库级静态分析 Dashboard。
AI Debt 不是技术债扫描器。
AI Debt 也不只是问答测验插件。
AI Debt 是面向 AI Builder 的 Session 级认知债管理工具。
```

和主要相邻项目的差异：

```text
AIDebtLens：看代码里留下了什么债。
WHY Plugin：问你是否理解这段代码。
Cognitive Coverage：看项目理解覆盖率。
AI Debt：记录 AI Build 过程中你欠下的认知债，并在合适时机帮你偿还。
```

---

# 15. MVP 设计

## 14.1 MVP 目标

第一版只验证两个核心假设：

```text
1. 用户愿意让工具在 AI Build 中静默记录认知债。
2. 用户愿意在 Idle Timeout / Pending Review 后接受一个 30 秒复盘入口。
```

MVP 不验证：

- repo-level dashboard
- 技术债扫描器
- 复杂知识图谱
- 团队治理流程
- 完整课程系统
- 复杂桌宠生态 / 跨平台浮动 Companion

---

## 14.2 MVP 范围

优先支持：

```text
Claude Code Hook
Stop / PostToolUse Journal
Idle Timeout 逻辑结算
Local Build Journal Store
Cognitive Debt Marking
Pending Review
L0-L2 基础模式
Learning Inbox
Debt Ledger
Terminal Companion 气泡提示
Markdown Export
```

MVP 学习模式：

```text
L0 静默记录
L1 30 秒速记
L2 学一个重点
```

L3/L4 可以先用 Markdown 形式手动生成，不需要完整 UI。

---

## 14.3 MVP 工作流

```text
用户使用 Claude Code / Codex Build
        ↓
PostToolUse / Stop 持续写入 events.jsonl
        ↓
Stop 阶段轻度更新 debt_candidates.json
        ↓
Idle Timeout：15min 标记 idle，30min 触发深度分析
        ↓
生成 Pending Review + 写入 Learning Inbox
        ↓
用户通过 Terminal Companion 气泡 / CLI / Command 查看 L1
        ↓
用户选择：跳过 / 30 秒速记 / 学一个重点
        ↓
未处理内容进入 Debt Ledger
        ↓
后续通过 Grasp Check 偿还
```

---

## 14.4 MVP 输出示例

Idle Timeout 后生成的 Pending Review：

```text
AI Debt 已完成本次 Build 的认知债分析。

记录到 3 个认知债：

P1：Hook / Skill / MCP 边界
来源：AI 替你完成了工具架构分层判断。
风险：如果不理解，后续插件设计会职责混乱。

P1：Idle Timeout 触发策略
来源：AI 替你判断 SessionEnd 不可靠，应采用 Journal-first 设计。
风险：如果不理解，系统可能漏记用户 kill terminal 前的 Build Trace。

P2：Companion UI 边界
来源：AI 建议宠物只作为低打扰提示层。
风险：如果把宠物当产品本体，会削弱认知债系统价值。

[跳过并记录] [30 秒速记] [学一个重点]
```

---

## 14.5 MVP Terminal Companion 事件

MVP 不需要完整自研浮动桌宠。应先输出标准事件，由 Terminal Companion 消费；后续再让 Petdex / OpenPets / 自研 Desktop Companion Adapter 消费：

```json
{
  "type": "pending_review",
  "debt_count": 3,
  "top_debt": "Hook / Skill / MCP 边界",
  "priority": "P1",
  "actions": ["brief", "learn_one", "later"],
  "ui_target": "terminal_companion"
}
```

---

# 16. 版本路线图

## v0.1：Journal-first Local MVP

```text
Claude Code Hook
Stop / PostToolUse Journal
Local Build Journal Store
Idle Timeout Pending Review
L0/L1 基础输出
Debt Ledger
```

## v0.2：L2 Learn-one + Grasp Check

```text
学一个重点
WHAT / HOW / WHY 问题生成
用户回答评估
债务状态更新
resolved / partial / unverified
```

## v0.3：Learning Inbox + Repeated Debt

```text
重复债务聚合
seen_count
priority ranking
weekly review
L4 学习路径 Markdown
```

## v0.4：Codex / Cursor Adapter

```text
Codex Stop Hook
Cursor workflow integration
通用 transcript import
orphaned journal recovery
```

## v0.5：MCP + Skill Packaging

```text
ai-debt-mcp
Claude Code Skill
Plugin packaging
Commands
Terminal Companion event API
```

## v0.6：Terminal Companion UI

```text
Claude Code TUI bubble
Idle Review Bubble
Debt Count Badge
High-risk Debt Nudge
Learn-one Entry
Command shortcuts
```

## v0.7：Optional Desktop Companion Adapter

```text
Petdex / OpenPets adapter
Custom floating pet adapter
Cross-tool companion event bridge
```

## v0.8：Optional Dashboard

```text
债务趋势
概念聚类
掌握状态
项目维度统计
```

注意：Dashboard 和完整浮动 Companion 是后续能力，不是 MVP 核心。MVP 只做终端嵌入式 Companion 或 CLI fallback。

---

# 17. 安全与隐私

## 16.1 风险

AI Debt 会采集：

- 对话记录
- 源码 diff
- 终端日志
- 错误堆栈
- 工具调用
- 项目结构
- 用户学习画像

因此必须 Local-first。

---

## 16.2 安全原则

| 原则 | 说明 |
|---|---|
| Local-first | 默认本地存储和分析 |
| 最小权限 | 默认只读，写操作只限本地 Ledger |
| Secret 清洗 | 采集前扫描 API Key、Token、私钥、Cookie |
| 项目级配置 | 用户可排除目录和文件 |
| 可删除 | 用户可删除任意 Session / Debt |
| 不执行任意 shell | MCP 不暴露通用命令执行能力 |
| 审计日志 | 记录所有 Ledger 更新和导出操作 |

---

# 18. 示例配置

```yaml
ai_debt:
  mode_system: L0-L4
  default_mode: L0

  product_focus:
    core: cognitive_debt
    technical_debt: signal_only
    realtime_teaching: false
    strategy: "capture_first_learn_on_demand_review_after_build"

  privacy:
    local_first: true
    cloud_sync: false
    secret_scan: true
    exclude_paths:
      - ".env"
      - "secrets/"
      - "node_modules/"
      - "dist/"

  triggers:
    journal_first: true
    capture_on_user_prompt_submit: true
    capture_post_tool_use: true
    capture_on_stop: true
    session_end_as_bonus_trigger: true
    idle:
      mark_idle_after_minutes: 15
      analyze_after_minutes: 30
      regenerate_if_resumed: true
    recovery:
      recover_orphaned_journal_on_startup: true

  review:
    default_level: L1
    max_debts_per_review: 3
    max_l2_debts_per_session: 1
    p0_always_notify: true
    p1_notify_in_l1: true
    p2_archive_only: true

  ledger:
    merge_similar_debts: true
    similarity_threshold: 0.8
    review_repeat_threshold: 3

  companion:
    enabled: false
    provider: "event_api"
    stop_phase_popup: false
    idle_popup_once: true
    p2_popup: false
    suppress_after_later_hours: 24
```

---

# 19. 评估指标

## 18.1 产品指标

| 指标 | 含义 |
|---|---|
| Journal Capture Success Rate | Stop / ToolUse 事件是否成功写入 journal |
| Pending Review Open Rate | 用户是否打开 Idle Timeout 后的 L1 复盘 |
| Debt Save Rate | 债务是否被保存 |
| L2 Learn-One Rate | 用户是否选择学习一个重点 |
| Inbox Return Rate | 用户是否回到 Inbox 偿还债务 |
| Idle Analysis Success Rate | Idle Timeout 后是否成功生成 pending review |
| Companion Prompt Click Rate | 宠物气泡提示是否被点击 |
| Debt Resolution Rate | 认知债销账比例 |
| Repeat Debt Detection | 重复债务识别率 |

---

## 18.2 学习指标

| 指标 | 含义 |
|---|---|
| Grasp Check Pass Rate | 用户通过掌握度验证的比例 |
| Repeated Confusion Rate | 同一概念反复未掌握比例 |
| Debug Readiness | 用户是否知道出错后从哪里查 |
| Transfer Ability | 用户是否能迁移到新场景 |
| Manual Reproduction Rate | 用户能否在 AI 不在时复现关键逻辑 |

---

# 20. 风险与对策

## 19.1 用户觉得烦

风险：如果系统实时教学，用户会关闭。

对策：

```text
主形态干中记，事后学；
构建中默认 silent；
只在高风险或重复债务时 soft hint。
```

---

## 19.2 认知债误报

风险：系统把用户已经理解的内容记为债务。

对策：

```text
必须有 evidence；
允许用户标记“已掌握”；
通过 Grasp Check 验证；
低置信度债务只归档不提醒。
```

---

## 19.3 变成普通技术债工具

风险：产品滑向 repo-level scanner，与 AIDebtLens / ai-debt-scanner 同质化。

对策：

```text
技术债只作为信号；
核心输出永远围绕用户是否理解；
MVP 不做 repo dashboard。
```

---

## 19.4 隐私风险

风险：采集公司代码、日志、密钥、私有架构信息。

对策：

```text
Local-first；
Secret scan；
排除路径；
不默认云同步；
可删除；
最小权限。
```

---


## 19.5 依赖 SessionEnd 导致漏记

风险：用户直接 kill terminal，SessionEnd 未触发，导致认知债没有被记录。

对策：

```text
采用 Journal-first；
Stop / PostToolUse 持续落盘；
Idle Timeout 作为逻辑结算点；
下次启动恢复 orphaned journal。
```

---

## 19.6 Companion UI 变成玩具或骚扰源

风险：Companion UI 过度可爱、过度动画化或频繁弹窗，削弱 AI Debt 的工程工具属性。

对策：

```text
Companion 只是终端提示层 / Ambient UI，不是产品本体；
默认低饱和、低频、可关闭；
Stop 阶段不弹；
Idle 后最多弹一次；
P2 不弹；
用户选择“稍后”后当天不再提示。
```

---

# 21. 最终设计总结

AI Debt v5 的最终形态是：

```text
AI Build 过程中的认知债黑匣子 + 按需学习系统。
```

它不主打实时教学，也不主打技术债扫描。

它的核心产品公式是：

```text
AI Debt = 默认干中记 + 按需干中学 + 事后集中学
```

工程实现公式是：

```text
AI Debt = Journal-first + Stop Light Analysis + Idle Settlement + Debt Ledger
```

核心闭环：

```text
AI Build
  ↓
干中记：Build Journal + AI Delegation Audit
  ↓
轻分析：Stop 阶段更新候选认知债
  ↓
逻辑结算：Idle Timeout 深分析
  ↓
事后看：Pending Review + L1 30 秒速记
  ↓
按需学：L2 / L3 / L4
  ↓
验证掌握：Grasp Check
  ↓
长期管理：Debt Ledger + Learning Inbox
```

前台体验：

```text
CLI / Command 是工程主入口；
Terminal Companion 是低打扰提示入口；Desktop Pet 只是后续可选增强；
Markdown / Web / Dashboard 是深度复盘入口。
```

最终产品定义：

> **AI Debt 是一个面向 AI Builder 的 Session 级认知债管理工具。它在 AI Build 过程中以 Journal-first 方式静默记录 AI 代劳造成的理解债和意图债，在 Stop 阶段进行轻度分析，在 Idle Timeout 后进行深度分析并生成 Pending Review。用户可通过 L0-L4 模式按需查看、学习、验证和偿还认知债，从而在使用 AI 提效的同时保留长期理解、判断和掌控能力。**

---

# 22. 参考项目补充

## 21.1 Companion / Pet UI 相关

| 项目 | 相关性 | 可借鉴点 | 对 AI Debt 的启示 |
|---|---|---|---|
| `crazyma99/claude-minipet` | Claude Code 终端内虚拟宠物 | Claude Code hooks、daemon、终端底部 TUI 气泡、Unicode/ANSI 渲染 | 最适合借鉴 MVP 形态，但它更偏 Claude Code 专用，不天然多工具 |
| `crafter-station/petdex` | Agent 宠物图库 / 桌面宠物生态 | 宠物图库、CLI 安装、响应 Codex / Claude Code / OpenCode / Gemini CLI 活动的浮层形态 | 多工具和生态化能力较强，但浮动桌宠复杂度高，适合后续 Adapter |
| `alvinunreal/openpets` | 面向 AI coding agents 的桌面宠物平台 | Desktop companion、Plugin SDK、MCP、Claude Code / OpenCode / Cursor 等集成 | 可作为后续 Desktop Companion Adapter 参考，不应进入 MVP 主线 |

设计结论：AI Debt v0.1-v0.2 优先做 **Terminal-embedded Companion**，借鉴 claude-minipet 的终端气泡形态；Petdex / OpenPets 代表的浮动桌宠和插件生态作为后续可选 UI Adapter，而不是核心产品本体。

参考链接：

- claude-minipet: https://github.com/crazyma99/claude-minipet
- Petdex: https://github.com/crafter-station/petdex
- OpenPets: https://github.com/alvinunreal/openpets
- OpenPets Docs: https://openpets.dev/docs

---
