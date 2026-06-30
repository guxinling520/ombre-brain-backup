"""
Diary sync: auto-import un-imported diary entries into Ombre-Brain.
Uses hold (not grow) to preserve exact text with date+time.
"""
import os, sys, re, json, httpx, glob
from pathlib import Path
from datetime import datetime

OMBRE_URL = "http://127.0.0.1:8001/mcp"
DIARY_DIR = Path("C:/Users/Lenovo/.cyberboss/diary")
MARKER_DIR = Path("C:/Users/Lenovo/.cyberboss/ombre-brain/.sync_markers")
MARKER_DIR.mkdir(parents=True, exist_ok=True)

def mcp_call(session_id, method, params):
    """Call an MCP tool and return the text result."""
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": method, "arguments": params}
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = httpx.post(OMBRE_URL, content=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }, timeout=60)
    resp_text = r.content.decode("utf-8", errors="replace")
    m = re.search(r'"text":"([^"]+)"', resp_text)
    return m.group(1) if m else r.status_code

def init_session():
    r = httpx.post(OMBRE_URL, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "diary-sync", "version": "1.0"}
        }
    }, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    })
    return r.headers.get("mcp-session-id")

def get_imported_dates():
    """Read which dates have already been imported."""
    imported = set()
    for f in MARKER_DIR.glob("*.marker"):
        imported.add(f.stem)
    return imported

def needs_import(diary_file):
    """No marker → needs import. Today → always re-process (skips dupes via section tracker)."""
    marker = MARKER_DIR / f"{diary_file.stem}.marker"
    if not marker.exists():
        return True
    today = datetime.now().strftime("%Y-%m-%d")
    return diary_file.stem == today

def mark_imported(date_str):
    (MARKER_DIR / f"{date_str}.marker").touch()

SECTION_TRACKER = MARKER_DIR / "sections_today.json"

def load_section_tracker():
    try:
        return json.loads(SECTION_TRACKER.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_section_tracker(tracker):
    SECTION_TRACKER.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")

def parse_sections(content, date_str):
    """Split diary markdown into time-stamped sections."""
    lines = content.split("\n")
    sections = []
    current_time = None
    current_lines = []

    for line in lines:
        m = re.match(r"^## (\d{2}:\d{2})(.*)", line)
        if m:
            # Save previous section
            if current_time is not None:
                text = " ".join(l.strip() for l in current_lines if l.strip())
                if text:
                    sections.append((current_time, text))
            # Start new section
            current_time = m.group(1)
            rest = m.group(2).strip()
            current_lines = [rest] if rest else []
        else:
            if current_time is not None:
                current_lines.append(line)
            # Skip content before first ## header

    # Last section
    if current_time is not None:
        text = " ".join(l.strip() for l in current_lines if l.strip())
        if text:
            sections.append((current_time, text))

    return sections

def main():
    imported = get_imported_dates()
    diary_files = sorted(DIARY_DIR.glob("2026-*.md"))
    to_import = [f for f in diary_files if needs_import(f)]

    if not to_import:
        print("[sync] All diaries already synced.")
        return

    sid = init_session()
    if not sid:
        print("[sync] Failed to init MCP session")
        return

    for f in to_import:
        date_str = f.stem
        content = f.read_text(encoding="utf-8")
        if not content.strip():
            mark_imported(date_str)
            continue

        # Strip non-GBK chars to avoid print crashes
        safe_content = content.encode("gbk", errors="ignore").decode("gbk", errors="ignore")
        sections = parse_sections(safe_content, date_str)

        if not sections:
            mark_imported(date_str)
            print(f"[sync] {date_str} -> no sections found, skipped.")
            continue

        # For today, only import NEW sections (avoid duplicates)
        today = datetime.now().strftime("%Y-%m-%d")
        tracker = load_section_tracker()
        imported_times = set(tracker.get(date_str, []))
        to_hold = [(t, txt) for t, txt in sections if t not in imported_times]
        newly_imported = []

        ok = 0
        for time_str, text in to_hold:
            entry = f"{date_str} {time_str} - {text}"
            try:
                result = mcp_call(sid, "hold", {
                    "content": entry,
                    "tags": "日记",
                    "importance": 5
                })
                ok += 1
                newly_imported.append(time_str)
            except Exception as e:
                msg = str(e).encode("gbk", errors="ignore").decode("gbk", errors="ignore")
                print(f"[sync] {date_str} {time_str} -> FAILED: {msg}")

        if newly_imported:
            tracker[date_str] = list(imported_times | set(newly_imported))
            save_section_tracker(tracker)

        mark_imported(date_str)
        if ok:
            print(f"[sync] {date_str} -> {ok}/{len(to_hold)} new sections imported (total {len(sections)}).")

if __name__ == "__main__":
    main()
