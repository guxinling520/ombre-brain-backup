# 自运链路

## 常驻服务（Ombre Brain server）
`python3 .../ombre-brain/src/server.py` — 1 个进程管所有后台任务

| 模块 | 职责 | 频率 |
|------|------|------|
| MCP 工具 | breath/hold/grow/trace/anchor 等 11 个工具 | 按需 |
| HTTP dashboard | 管理面板 (:8001) | 常驻 |
| 日记同步线程 | 扫描 `diary/` → `hold` 到 OB 记忆 → 更新 timeline | 每 120 秒 |
| 闹钟桥接 | 扫描 `reminder-queue.json` → 到期提醒推 MacroDroid → 手机响铃 | 每 120 秒 |
| baseline 搜索 | BM25 搜索 baseline/ 文件（替代旧 vector-memory server） | 启动时建索引 |
| GitHub 备份 | `buckets/` + `diary/` → `guxinling520/ombre-brain-backup` | 每 60 分钟 |

不再有独立的 vector-memory server、sync_scheduler 进程。

## 定时任务（Windows Scheduled Task）
每天 00:30 / 12:30 → `auto-maintain.ps1`
1. `archive-chats.py` — 归档聊天记录
2. `diary-to-timeline.mjs --missing` — 时间轴补漏
3. `update-context.py` — 刷新 `context/recent.md`
4. 生成 `.baseline-pending.md` — 标记待抽取到 baseline
5. `reminder-alarm-bridge.py` — 到期提醒→手机闹钟

## 触发同步（AI 写日记时）
- `triggerDiaryToTimeline` → `diary-to-timeline.mjs`
- 重建时间轴站点
- 写入 `.last-sync.md` 同步状态
