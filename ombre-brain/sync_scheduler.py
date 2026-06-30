"""
Auto sync scheduler: polls for new diary entries and imports to OB via hold.
Runs in background alongside the OB server.
"""
import os, sys, re, json, httpx, glob, time, subprocess
from pathlib import Path
from datetime import datetime

OMBRE_URL = "http://127.0.0.1:8001/mcp"
DIARY_DIR = Path("C:/Users/Lenovo/.cyberboss/diary")
MARKER_DIR = Path("C:/Users/Lenovo/.cyberboss/ombre-brain/.sync_markers")
MARKER_DIR.mkdir(parents=True, exist_ok=True)
POLL_INTERVAL = 120  # 2 minutes - fast enough to feel near real-time without wasting API calls
DIARY_TO_TIMELINE = "C:/Users/Lenovo/.cyberboss/diary-to-timeline.mjs"

def mcp_call(sid, method, params):
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
            "Mcp-Session-Id": sid
        }, timeout=60)
    resp_text = r.content.decode("utf-8", errors="replace")
    m = re.search(r'"text":"([^"]*)"', resp_text)
    return m.group(1)[:60] if m else f"HTTP {r.status_code}"

def new_session():
    try:
        r = httpx.post(OMBRE_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "sync-scheduler", "version": "1.0"}
            }
        }, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }, timeout=10)
        return r.headers.get("mcp-session-id")
    except Exception:
        return None

SECTION_TRACKER = MARKER_DIR / "sections_today.json"

def get_imported():
    return {f.stem for f in MARKER_DIR.glob("*.marker")}

def load_section_tracker():
    """Load per-section import tracker (avoids duplicates for today's growing diary)."""
    try:
        return json.loads(SECTION_TRACKER.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_section_tracker(tracker):
    SECTION_TRACKER.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")

def needs_import(diary_file):
    """Past dates: marker check only.  Today: always process for new sections."""
    marker = MARKER_DIR / f"{diary_file.stem}.marker"
    if not marker.exists():
        return True
    today = datetime.now().strftime("%Y-%m-%d")
    return diary_file.stem == today

def touch_marker(date_str):
    (MARKER_DIR / f"{date_str}.marker").touch()

def parse_sections(content):
    """Split diary markdown into time-stamped sections."""
    lines = content.split("\n")
    sections = []
    current_time = None
    current_lines = []

    for line in lines:
        m = re.match(r"^## (\d{2}:\d{2})(.*)", line)
        if m:
            if current_time is not None:
                text = " ".join(l.strip() for l in current_lines if l.strip())
                if text:
                    sections.append((current_time, text))
            current_time = m.group(1)
            rest = m.group(2).strip()
            current_lines = [rest] if rest else []
        else:
            if current_time is not None:
                current_lines.append(line)

    if current_time is not None:
        text = " ".join(l.strip() for l in current_lines if l.strip())
        if text:
            sections.append((current_time, text))

    return sections

def wait_for_server():
    for i in range(30):
        try:
            sid = new_session()
            if sid:
                return sid
        except Exception:
            pass
        time.sleep(2)
    return None

def sync_loop():
    print("[sync] Waiting for OB server...", flush=True)
    sid = wait_for_server()
    if not sid:
        print("[sync] Server not available after 60s, giving up.", flush=True)
        return

    print(f"[sync] Connected. Polling every {POLL_INTERVAL}s.", flush=True)
    while True:
        try:
            imported = get_imported()
            diary_files = sorted(DIARY_DIR.glob("2026-*.md"))
            to_import = [f for f in diary_files if needs_import(f)]

            for f in to_import:
                date_str = f.stem
                content = f.read_text(encoding="utf-8")
                if not content.strip():
                    touch_marker(date_str)
                    continue

                safe_content = content.encode("gbk", errors="ignore").decode("gbk", errors="ignore")
                sections = parse_sections(safe_content)

                if not sections:
                    touch_marker(date_str)
                    print(f"[sync] {date_str} -> no sections found, skipped.", flush=True)
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
                        mcp_call(sid, "hold", {
                            "content": entry,
                            "tags": "日记",
                            "importance": 5
                        })
                        ok += 1
                        newly_imported.append(time_str)
                    except Exception as e:
                        msg = str(e).encode("gbk", errors="ignore").decode("gbk", errors="ignore")
                        print(f"[sync] {date_str} {time_str} -> FAILED: {msg}", flush=True)

                # Update tracker with newly imported section times
                if newly_imported:
                    tracker[date_str] = list(imported_times | set(newly_imported))
                    save_section_tracker(tracker)

                touch_marker(date_str)
                total = len(sections)
                if ok:
                    print(f"[sync] {date_str} -> {ok}/{len(to_hold)} new sections imported (total {total}).", flush=True)

                # Also trigger timeline sync after import
                try:
                    subprocess.run(
                        ["node", DIARY_TO_TIMELINE, "--missing"],
                        capture_output=True, text=True, timeout=60,
                        cwd=str(Path(DIARY_TO_TIMELINE).parent)
                    )
                except Exception:
                    pass

            # Also run reminder→alarm bridge (every cycle, lightweight)
            try:
                subprocess.run(
                    [sys.executable, str(Path("C:/Users/Lenovo/.cyberboss/scripts/reminder-alarm-bridge.py"))],
                    capture_output=True, text=True, timeout=30,
                )
            except Exception:
                pass

            if not to_import:
                print(f"[sync] Poll at {datetime.now():%H:%M} - nothing new.", flush=True)

        except Exception as e:
            msg = str(e).encode("gbk", errors="ignore").decode("gbk", errors="ignore")
            print(f"[sync] Error: {msg}", flush=True)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    sync_loop()
