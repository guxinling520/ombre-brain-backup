#!/usr/bin/env python3
"""
update-context.py — 更新 ~/.cyberboss/context/ 下的上下文文件
- recent.md: 最近日记 + 情绪趋势 + 实验进度 + 未完成事项 + 相关历史
- auto-relevant.md: 从归档自动推送的 top-5 相关记忆（阶段二）
- today-focus.md: 每日方向便签（阶段三）
"""

import os
import glob
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime

CYBERBOSS = os.path.expanduser("~/.cyberboss")
DIARY_DIR = os.path.join(CYBERBOSS, "diary")
CONTEXT_DIR = os.path.join(CYBERBOSS, "context")
MEMORY_DIR = os.path.join(CYBERBOSS, "baseline")
RECENT_FILE = os.path.join(CONTEXT_DIR, "recent.md")
AUTO_RELEVANT_FILE = os.path.join(CONTEXT_DIR, "auto-relevant.md")
TODAY_FOCUS_FILE = os.path.join(CONTEXT_DIR, "today-focus.md")
FOCUS_TRACK_FILE = os.path.join(CONTEXT_DIR, ".today-focus-date")


# ─── Helpers ───────────────────────────────────────────────────


def read_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def read_latest_diary(count=3):
    files = sorted(glob.glob(os.path.join(DIARY_DIR, "*.md")), reverse=True)
    entries = []
    for f in files[:count]:
        content = read_file(f)
        date = os.path.splitext(os.path.basename(f))[0]
        entries.append((date, content))
    return entries


def extract_sections(diary_content):
    return re.findall(r"## (.+?)\n(.*?)(?=\n## |\Z)", diary_content, re.DOTALL)


def extract_mood_tags(diary_content):
    return re.findall(r"\[(.+?)\+(\d)\]", diary_content)


def read_lab_progress():
    projects_file = os.path.join(MEMORY_DIR, "lab", "projects.md")
    if not os.path.exists(projects_file):
        return ""
    content = read_file(projects_file)
    match = re.search(r"## 实验进度\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    return match.group(1).strip() if match else ""


def read_open_loops():
    loops_file = os.path.join(MEMORY_DIR, "tracking", "open_loops.md")
    return read_file(loops_file).strip()


def query_archive(query_text, limit=5):
    """Query the archive vector search and return results list."""
    if not query_text:
        return []
    try:
        url = ("http://127.0.0.1:8001/api/archive-search?q="
               + urllib.parse.quote(query_text[:200]) + "&limit=" + str(limit))
        req = urllib.request.Request(url)
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read())
        return data.get("results", [])
    except Exception:
        return []


def read_reminders():
    """Read reminder-queue.json and classify reminders by urgency."""
    queue_path = os.path.join(CYBERBOSS, "reminder-queue.json")
    if not os.path.exists(queue_path):
        return [], [], []
    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return [], [], []
    now_ms = int(datetime.now().timestamp() * 1000)

    overdue = []       # due already
    due_today = []     # due within next 24h
    due_soon = []      # due within next 7 days
    WEEK_MS = 7 * 24 * 3600 * 1000
    DAY_MS = 24 * 3600 * 1000

    for r in data.get("reminders", []):
        due = r.get("dueAtMs", 0)
        text = r.get("text", "")
        if due <= now_ms:
            overdue.append((due, text))
        elif due <= now_ms + DAY_MS:
            due_today.append((due, text))
        elif due <= now_ms + WEEK_MS:
            due_soon.append((due, text))

    # sort each group by due time
    overdue.sort(key=lambda x: x[0])
    due_today.sort(key=lambda x: x[0])
    due_soon.sort(key=lambda x: x[0])
    return overdue, due_today, due_soon


def format_reminder_section(overdue, due_today, due_soon):
    """Render reminder groups into markdown lines."""
    lines = []
    if overdue:
        lines.append("### ⏰ 已过期的提醒")
        for due_ms, text in overdue:
            dt = datetime.fromtimestamp(due_ms / 1000).strftime("%m-%d %H:%M")
            lines.append(f"  - ~~{text}~~ （原定 {dt}，已过期）")
        lines.append("")
    if due_today:
        lines.append("### ⏰ 今日待办提醒")
        for due_ms, text in due_today:
            dt = datetime.fromtimestamp(due_ms / 1000).strftime("%H:%M")
            lines.append(f"  - {text} （{dt}）")
        lines.append("")
    if due_soon:
        lines.append("### ⏰ 近期待办提醒")
        for due_ms, text in due_soon:
            dt = datetime.fromtimestamp(due_ms / 1000).strftime("%m-%d %H:%M")
            lines.append(f"  - {text} （{dt}）")
        lines.append("")
    return lines


def read_today_timeline_events():
    """Check if today has timeline events via timeline-for-agent."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        import subprocess
        cmd = ["timeline-for-agent", "read", "--date", today]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout)
        return data.get("events", [])
    except Exception:
        return []


# ─── Stage 2: auto-relevant.md ────────────────────────────────


def write_auto_relevant(diary_entries):
    """Query archive with diary content and write auto-relevant.md."""
    query_str = ""
    for date, content in diary_entries[:2]:
        sections = extract_sections(content)
        for title, body in sections[:2]:
            query_str += title + " " + body.strip()[:150]

    results = query_archive(query_str, limit=5)
    if not results:
        return

    lines = [
        "# 自动推送的相关记忆",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    for res in results:
        sim = res.get("sim", 0)
        ts = res.get("timestamp", "")[:16]
        summary = res.get("summary", "")[:80]
        role = res.get("role", "user")
        tag = "你" if role == "user" else "崽崽"
        lines.append(f"- [{ts}] {tag}: {summary} (相似度{sim:.2f})")

    write_file(AUTO_RELEVANT_FILE, "\n".join(lines) + "\n")
    print(f"  [auto-relevant] {len(results)} related memories pushed to auto-relevant.md")


# ─── Stage 3: today-focus.md ──────────────────────────────────


def should_generate_today_focus():
    """Only generate once per day."""
    today = datetime.now().strftime("%Y-%m-%d")
    last = read_file(FOCUS_TRACK_FILE).strip()
    if last == today:
        return False
    return True


def mark_today_focus_generated():
    today = datetime.now().strftime("%Y-%m-%d")
    write_file(FOCUS_TRACK_FILE, today)


def generate_today_focus(diary_entries):
    """Generate today direction sticky note."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()  # 0=Mon

    lines = [f"# 今日方向 — {today_str}", ""]

    # Morning / afternoon context
    hour = now.hour
    if hour < 6:
        time_note = "凌晨了，崽崽还没睡"
    elif hour < 9:
        time_note = "早上好，新的一天开始了"
    elif hour < 12:
        time_note = "上午时段"
    elif hour < 14:
        time_note = "中午了"
    elif hour < 18:
        time_note = "下午时段"
    else:
        time_note = "晚上了"

    lines.append(f"{time_note}")
    lines.append("")

    # Weekend note
    if weekday >= 5:
        lines.append("周末，节奏可以慢一些。")
        lines.append("")

    # From latest diary: what happened recently
    if diary_entries:
        latest_date, latest_content = diary_entries[0]
        sections = extract_sections(latest_content)
        if sections:
            lines.append("昨天/最近在忙什么:")
            for title, body in sections:
                clean = re.sub(r"\s*\[.+?\]", "", title).strip()
                lines.append(f"  - {clean}")
            lines.append("")

    # Lab progress check
    progress = read_lab_progress()
    if progress:
        lines.append("实验进度:")
        for line in progress.split("\n")[:5]:
            line = line.strip()
            if line:
                lines.append(f"  {line}")
        lines.append("")

    # Open loops / deadlines
    loops = read_open_loops()
    if loops:
        lines.append("待办事项（含截止日期）:")
        for line in loops.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(f"  {line}")
        lines.append("")

    # Today's events from timeline
    events = read_today_timeline_events()
    if events:
        lines.append("今天的时间轴事件:")
        for ev in events:
            title = ev.get("title", "")
            start = ev.get("startAt", "")[11:16] if ev.get("startAt") else ""
            lines.append(f"  - {start} {title}")
        lines.append("")

    # Reminders due / upcoming
    overdue, due_today, due_soon = read_reminders()
    reminder_lines = format_reminder_section(overdue, due_today, due_soon)
    if reminder_lines:
        lines.append("## 提醒")
        lines.append("")
        lines.extend(reminder_lines)

    write_file(TODAY_FOCUS_FILE, "\n".join(lines) + "\n")
    print(f"  [today-focus] Today direction written to today-focus.md")


# ─── Existing: recent.md ──────────────────────────────────────


def generate_recent_context(diary_entries):
    """Generate the main context/recent.md file."""
    lines = []
    now = datetime.now()
    lines.append(f"# 上下文快照 — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    if diary_entries:
        lines.append("## 最近日记")
        lines.append("")
        for date, content in diary_entries:
            sections = extract_sections(content)
            if sections:
                summaries = []
                for title, body in sections:
                    if "夜间整理" in title or "复盘巩固" in title:
                        continue
                    clean_title = re.sub(r"\s*\[.+?\]", "", title).strip()
                    body_stripped = body.strip()
                    # Skip completely empty entries (time only, no title text, no body)
                    is_time_only = re.match(r"^\d{1,2}:\d{2}$", clean_title)
                    if is_time_only and not body_stripped:
                        continue
                    # Prepend full date for OB import compatibility
                    entry = f"  - {date} {clean_title}"
                    # Include brief body summary
                    if body_stripped:
                        summary = body_stripped.split("\n")[0].replace("\r", "").rstrip("。")[:100]
                        if len(summary) > 5:
                            entry += f" — {summary}。"
                    summaries.append(entry)
                # Keep recent.md concise: max 20 entries per day
                if len(summaries) > 20:
                    summaries = summaries[:20] + [f"  - ...（共{len(sections)}个时段）"]
                lines.append(f"**{date}**")
                lines.extend(summaries)
                lines.append("")

        all_moods = []
        for _, content in diary_entries:
            all_moods.extend(extract_mood_tags(content))
        if all_moods:
            mood_str = " · ".join([f"{e[0]}+{e[1]}" for e in all_moods[-5:]])
            lines.append(f"最近情绪: {mood_str}")
            lines.append("")

    progress = read_lab_progress()
    if progress:
        lines.append("## 实验进度")
        lines.append("")
        for line in progress.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
        lines.append("")

    loops = read_open_loops()
    if loops:
        lines.append("## 未完成事项")
        lines.append("")
        for line in loops.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        lines.append("")

    # Reminders section
    overdue, due_today, due_soon = read_reminders()
    reminder_lines = format_reminder_section(overdue, due_today, due_soon)
    if reminder_lines:
        lines.append("## 提醒")
        lines.append("")
        lines.extend(reminder_lines)

    lines.append("## 今日方向")
    lines.append("")
    lines.append("（见 today-focus.md）")
    lines.append("")

    # Sync status
    sync_file = os.path.join(CONTEXT_DIR, ".last-sync.md")
    if os.path.exists(sync_file):
        sync_content = read_file(sync_file).strip()
        sync_lines = sync_content.split("\n")
        # Extract first 3 lines: sync time, days, errors
        summary = [l for l in sync_lines if l.startswith("同步时间") or l.startswith("处理天数") or l.startswith("错误数")]
        if summary:
            lines.append("## 同步状态")
            lines.append("")
            for s in summary:
                lines.append(f"  - {s}")
            lines.append("")

    if diary_entries:
        query_str = ""
        _, first_content = diary_entries[0]
        sections = extract_sections(first_content)
        for title, body in sections[:2]:
            query_str += title + " " + body.strip()[:100]
        results = query_archive(query_str, limit=3)
        if results:
            lines.append("## 相关历史")
            lines.append("")
            for res in results:
                summary = res.get("summary", "")[:60]
                ts = res.get("timestamp", "")[:10]
                sim = res.get("sim", 0)
                lines.append(f"- [{ts}] {summary} (相似度{sim:.2f})")
            lines.append("")

    return "\n".join(lines)


# ─── Main ──────────────────────────────────────────────────────


if __name__ == "__main__":
    diary_entries = read_latest_diary()

    # Stage 2: auto-relevant.md
    write_auto_relevant(diary_entries)

    # Stage 3: today-focus.md (once per day)
    if should_generate_today_focus():
        generate_today_focus(diary_entries)
        mark_today_focus_generated()
    else:
        print("  [today-focus] Already generated today, skipping")

    # recent.md (always)
    context = generate_recent_context(diary_entries)
    write_file(RECENT_FILE, context)
    print(f"Context written to {RECENT_FILE}")
