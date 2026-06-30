#!/usr/bin/env python3
"""
archive-chats.py — Stage 2: Full-text chat archiver
Scans JSONL session files, chunks by conversation turn,
embeds via vector service, and stores in SQLite for semantic search.
"""

import os, re, json, hashlib, sqlite3, urllib.request, glob
from datetime import datetime

CYBERBOSS = os.path.expanduser("~/.cyberboss")
PROJECTS_DIR = os.path.join(
    os.path.expanduser("~/.claude"), "projects",
    "F--cyberboss-new-cyberboss"
)
ARCHIVE_DIR = os.path.join(CYBERBOSS, "archive")
DB_PATH = os.path.join(ARCHIVE_DIR, "chats.db")
EMBED_URL = "http://127.0.0.1:8768/embed"

os.makedirs(ARCHIVE_DIR, exist_ok=True)

# ── DB ──────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("""
  CREATE TABLE IF NOT EXISTS chat_chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_idx   INTEGER NOT NULL,
    timestamp  TEXT,
    role       TEXT NOT NULL,       -- 'user' or 'assistant'
    content    TEXT NOT NULL,
    summary    TEXT,                -- first 80 chars as summary
    file_hash  TEXT NOT NULL,
    embedding  BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )
""")
conn.execute("""
  CREATE INDEX IF NOT EXISTS idx_chunks_session ON chat_chunks(session_id)
""")
conn.execute("""
  CREATE INDEX IF NOT EXISTS idx_chunks_time ON chat_chunks(timestamp)
""")
conn.commit()


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def get_processed_hashes():
    """return set of (session_id, file_hash) already in DB."""
    rows = conn.execute(
        "SELECT DISTINCT session_id, file_hash FROM chat_chunks"
    ).fetchall()
    return set(rows)


def extract_turns(jsonl_path):
    """Extract user/assistant turns from a JSONL file."""
    turns = []
    session_id = None

    with open(jsonl_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Try to get session_id from message
            sid = data.get("sessionId")
            if sid:
                session_id = sid

            msg_type = data.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            message = data.get("message", {})
            if isinstance(message, dict):
                role = message.get("role", msg_type)
                content_raw = message.get("content", "")
            else:
                role = msg_type
                content_raw = str(message) if message else ""

            # Extract text from assistant's content blocks (list of dicts)
            if isinstance(content_raw, list):
                texts = []
                for block in content_raw:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                content = "\n".join(texts)
            else:
                content = str(content_raw) if content_raw else ""

            # Skip empty or system-only messages
            if not content.strip():
                continue
            if len(content.strip()) < 5:
                continue

            ts = data.get("timestamp", "")
            # Parse timestamp
            if ts:
                try:
                    ts_parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except:
                    ts_parsed = None
            else:
                ts_parsed = None

            turns.append({
                "session_id": session_id or os.path.basename(jsonl_path),
                "role": role,
                "content": content.strip()[:2000],  # cap length
                "timestamp": ts,
                "timestamp_obj": ts_parsed,
            })

    return turns, session_id


def chunk_turns(turns):
    """Group consecutive user-assistant pairs into chunks."""
    chunks = []
    for i, t in enumerate(turns):
        summary = t["content"][:80].replace("\n", " ")
        chunks.append({
            "session_id": t["session_id"],
            "turn_idx": i,
            "timestamp": t["timestamp"],
            "role": t["role"],
            "content": t["content"],
            "summary": summary,
        })
    return chunks


def batch_embed(texts, batch_size=32):
    """Embed texts via vector service API."""
    all_embs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        data = json.dumps({"texts": batch}).encode()
        req = urllib.request.Request(
            EMBED_URL, data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            r = urllib.request.urlopen(req, timeout=120)
            resp = json.loads(r.read())
            all_embs.extend(resp["embeddings"])
        except Exception as e:
            print(f"  Embed batch error at {i}: {e}")
            # Return zero vectors as fallback
            for _ in batch:
                all_embs.append([0.0] * 512)
    return all_embs


def process_file(jsonl_path):
    """Process a single JSONL file and store chunks."""
    fhash = file_hash(jsonl_path)
    basename = os.path.basename(jsonl_path)

    print(f"\n[FILE] {basename}")

    turns, session_id = extract_turns(jsonl_path)
    if not turns:
        print("  No conversation turns found")
        return 0, 0

    chunks = chunk_turns(turns)
    print(f"  {len(turns)} turns → {len(chunks)} chunks")

    # Check against existing
    existing = get_processed_hashes()
    if session_id:
        key = (session_id, fhash)
        if key in existing:
            print(f"  Already processed (hash match)")
            return len(chunks), 0

    # Embed all chunk contents
    contents = [c["content"] for c in chunks]
    print(f"  Embedding {len(contents)} chunks…")
    embeddings = batch_embed(contents)

    # Store in DB
    conn.execute("BEGIN")
    count = 0
    for chunk, emb in zip(chunks, embeddings):
        import struct
        emb_blob = struct.pack(f"{len(emb)}f", *emb)
        conn.execute("""
            INSERT OR REPLACE INTO chat_chunks
                (session_id, turn_idx, timestamp, role, content, summary, file_hash, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chunk["session_id"], chunk["turn_idx"],
            chunk["timestamp"], chunk["role"],
            chunk["content"], chunk["summary"],
            fhash, emb_blob,
        ))
        count += 1
    conn.commit()
    print(f"  Stored {count} chunks")
    return len(chunks), count


def main():
    print("=" * 50)
    print("[Chat Archive]")
    print(f"   DB: {DB_PATH}")
    print(f"   Scanning: {PROJECTS_DIR}")
    print("=" * 50)

    # Find all JSONL files
    pattern = os.path.join(PROJECTS_DIR, "*.jsonl")
    files = sorted(glob.glob(pattern))

    # Also check subdirectory for current session files
    for sub in os.listdir(PROJECTS_DIR):
        subpath = os.path.join(PROJECTS_DIR, sub)
        if os.path.isdir(subpath):
            files.extend(glob.glob(os.path.join(subpath, "*.jsonl")))

    # Deduplicate
    files = sorted(set(f for f in files))

    print(f"\nFound JSONL files: {len(files)}")

    total_chunks = 0
    total_new = 0
    for fpath in files:
        c, n = process_file(fpath)
        total_chunks += c
        total_new += n

    # Stats
    print(f"\n{'=' * 50}")
    print(f"Done: {total_chunks} total chunks, {total_new} new stored")
    rows = conn.execute("SELECT COUNT(*) FROM chat_chunks").fetchone()
    print(f"DB total rows: {rows[0]}")

    # Show sample sessions
    sessions = conn.execute(
        "SELECT session_id, MIN(timestamp), COUNT(*) FROM chat_chunks GROUP BY session_id ORDER BY MIN(timestamp) DESC LIMIT 5"
    ).fetchall()
    print(f"\nLatest sessions:")
    for sid, ts, cnt in sessions:
        print(f"  {sid[:12]}…  {ts or '?'}  ({cnt} chunks)")


if __name__ == "__main__":
    main()
