#!/usr/bin/env python3
"""
reminder-alarm-bridge.py — 提醒队列 → 远程闹钟桥接

从 reminder-queue.json 读取即将到期的提醒，自动通过 MacroDroid webhook
向手机发送系统闹钟。防重复触发，每次只处理未闹过的提醒。
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

CYBERBOSS = os.path.expanduser("~/.cyberboss")
QUEUE_FILE = os.path.join(CYBERBOSS, "reminder-queue.json")
LOG_FILE = os.path.join(CYBERBOSS, "logs", "reminder-alarm-bridge.log")

# 手机 MacroDroid webhook（与 alarm-kit server.py 一致）
DEVICE_ID = "50461cf7-f3a2-44c1-aea9-e3bc35c9b43c"
ALARM_URL = f"https://trigger.macrodroid.com/{DEVICE_ID}/alarm"

# 配置
ALARM_WINDOW_MINUTES = 15      # 到期前多少分钟内触发闹钟
MAX_ALARM_MINUTES = 1440        # 最长闹钟时长（24 小时）


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fire_alarm(minutes):
    """调用 MacroDroid webhook 设 N 分钟后响铃的闹钟。"""
    params = urllib.parse.urlencode({"alarm_min": int(minutes)})
    url = f"{ALARM_URL}?{params}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return resp.status == 200, body[:100]
    except Exception as e:
        return False, str(e)


def main():
    if not os.path.exists(QUEUE_FILE):
        log("reminder-queue.json 不存在，跳过")
        return

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    reminders = data.get("reminders", [])
    if not reminders:
        return

    now_ms = int(time.time() * 1000)
    modified = False

    for r in reminders:
        # 跳过已触发过闹钟的
        if r.get("alarmed"):
            continue

        due_ms = r.get("dueAtMs", 0)
        if due_ms <= 0:
            continue

        delta_min = (due_ms - now_ms) / 60000.0

        # 过期超过 5 分钟的就不闹了（太晚了）
        if delta_min < -5:
            continue

        # 还远没到期的跳过
        if delta_min > ALARM_WINDOW_MINUTES:
            continue

        # 到期前窗口内 或 刚过期 → 触发闹钟
        alarm_min = max(0, int(round(delta_min)))
        if alarm_min > MAX_ALARM_MINUTES:
            continue

        text = r.get("text", "(无内容)")[:60]
        ok, resp_body = fire_alarm(alarm_min)

        if ok:
            r["alarmed"] = True
            r["alarmedAt"] = datetime.now(timezone.utc).isoformat()
            modified = True
            if alarm_min > 0:
                log(f"闹钟已触发 [{alarm_min}分钟后响]: {text}")
            else:
                log(f"闹钟已触发 [立即响]: {text}")
        else:
            log(f"闹钟触发失败 [alarm_min={alarm_min}]: {resp_body} — {text}")

    if modified:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"提醒队列已更新（{sum(1 for r in reminders if r.get('alarmed'))} 条已触发）")


if __name__ == "__main__":
    main()
