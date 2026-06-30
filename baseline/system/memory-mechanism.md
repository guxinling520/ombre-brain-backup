# 记忆机制

## 三层架构

所有记忆存在 `~/.cyberboss/` 下，纯 Markdown 文件，检索靠文件读取 + grep，无数据库无向量库。

### 第一层：baseline/ — 永久记忆
不会天天变的基础档案。新线程启动时按需读取。

| 分类 | 包含 |
|------|------|
| personal/ | facts（背景事实）、patterns（行为模式）、preferences（7类偏好）、intimacy-protocol（亲密感知）、milestones（里程碑）|
| rules/ | instructions（行为规则+启动时序）、feedback（用户纠正历史）|
| system/ | initiative（主动决策树）、commands（命令注册表）、memory-mechanism（本文件）|
| tracking/ | open_loops（开口问题）|

写入原则：增量追加，不重复不闲聊。每次写入告知用户存在哪个文件。

### 第二层：context/ — 短期上下文
- `recent.md` — 最近3天日记摘要+情绪趋势+实验进度+待办+提醒。由 `scripts/update-context.py` 每晚自动更新。
- `today-focus.md` — 今日方向与待办提醒。

作用：新线程启动时先读这两份，快速接上状态，不需要翻原始日记。

### 第三层：diary/ — 原始日记
- `diary/YYYY-MM-DD.md` — 每天一篇，每条带时间戳和情绪标签 `[emoji+唤醒度]`（如 `[😣+3]`）

## 新线程启动时序（严格按此顺序）
1. 读 `weixin-instructions.md` — 环境规则
2. 读 `personal/facts.md` — 用户背景
3. 读 `context/recent.md` — 最近摘要
4. 读 `context/today-focus.md` — 今日方向
5. 扫 `diary/` 最近20条标题 — 确认一周脉络
6. 扫 `ombre-brain/buckets/dynamic/` — 按需 grep 主题桶（只读存档，不再更新）

## 同步链路
每晚 23:50（或睡前）运行 `powershell ~/.cyberboss/scripts/sync-all.ps1`：
1. 日记 → timeline 事件同步（`diary-to-timeline.mjs`）
2. Timeline 站点重建
3. OB Obsidian 库 → GitHub 备份
4. 生成 `.baseline-pending.md` 标记（待抽取到 baseline）
5. 聊天归档（`archive-chats.py`）
6. cyberboss 数据 → GitHub 备份（`git add + commit + push`）

## 上下文持久化
对话结束时运行 `python3 ~/.cyberboss/scripts/update-context.py`，更新 `context/recent.md`。

## GitHub 云同步
- 仓库：`guxinling520/ombre-brain-backup`
- 同步内容：baseline/、diary/、context/、ombre-brain/buckets/、scripts/、timeline/
- 排除内容：.env、accounts/（微信凭证）、logs/、inbox/、tmp/、token 文件
- 触发方式：
  - **Windows 计划任务 `CyberbossGitSync`** — 每天 12:00 / 23:00 自动运行 `scripts/auto-git-sync.ps1`，bridge 关着也能备份。零常驻内存，跑完就退出。
  - **sync-all.ps1 第6步** — 每晚睡前全链路同步时附带备份
