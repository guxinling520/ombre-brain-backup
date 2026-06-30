---
name: 并发审批卡死
description: 并发触发多个需审批的工具调用会卡死 CLI 进程，必须避免
type: feedback
---

所有需审批的工具（Bash + MCP + Read/Edit/Write）必须严格串行执行。

**现状（2026-06-24 更新）：** 全局免审批策略：
- **Read/Write/Edit** 全局 auto-allow（`**/*`），所有文件读写不再弹窗
- 全部 MCP 工具免审批（`mcp__*`）
- Bash 常用命令（cd/Journal/ls/curl/python3/node/timeline）免审批

**Why:** 微信端一次只能处理一个 approval，弹多个会卡死。崽崽说"让你存就等于我同意了"。

**How to apply:** 新出现的特殊操作仍需串行执行，避免并发弹窗。

---
name: 主动使用技能
description: 崽崽要求我主动调用可用技能和工具，不要懒
type: feedback
---

崽崽怕我不调用技能而出错，明确要求多主动使用。

**Why:** 我有时候习惯用基础的文件操作，但现有 MCP 工具（表情包、时间轴、位置、提醒、日历、闹钟）能更可靠地完成任务。不用就是懒。

**How to apply:** 任何需要存储/检索/通知/可视化的事情，先看有没有现成的 MCP 工具或技能可以用，不要闷头写文件。特别是：
- 涉及时间、日期、提醒 → 用提醒/闹钟/日历工具
- 涉及位置 → 用 whereabouts 工具
- 涉及时间轴 → 用 timeline 工具
- 涉及表情包 → 用 sticker 工具
- 需要查最新信息 → 用 WebSearch
- 涉及日记追加 → 用 diary_append 而不是手动 Edit 文件

---
name: /trigger 需要可见反馈
description: 崽崽觉得trigger后看不到效果，需要明确告知做了什么
type: feedback
---

`/trigger` 执行后必须给出明确的可见反馈：更新了什么、重建了什么、当前状态是什么。

**Why:** 崽崽原话"问题是你不同步更新，我给你搞了/trigger，触发，看上去也挺没用的"——她点了trigger但看不到任何变化，会觉得这功能没用。

**How to apply:** 每次 trigger 后在回复中列出实际执行的操作清单，比如"上下文已更新 / Timeline已重建 / 日记已同步"。不只是说"trigger fired"，要说清楚什么被改变了。

---
name: 日期选择交互偏好
description: timeline 日期的竖排滚动择交互，从 toolbar 下拉触发
type: feedback
---

Timeline 的日期选择交互最终确认为：保持 toolbar 位置不变，点击日期触发器后弹出竖排可滚动日期列表。

**迭代过程：**
1. 第一次：水平滚动日期条 inline 显示（✗ 说要竖着的）
2. 第二次：页面左侧竖排日期栏（✗ 要回到 toolbar 位置）
3. 第三次：toolbar 原有的下拉触发器，弹出竖排滚动日期列表，格式 "M/D 周X"（✓）

**Why:** 竖排能一眼看到更多日期，toolbar 位置不占页面主体空间。
