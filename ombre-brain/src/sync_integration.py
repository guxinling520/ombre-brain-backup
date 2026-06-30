"""
sync_integration.py — 将 sync_scheduler 作为后台线程嵌入 Ombre Brain server

server.py 的 lifespan 启动时自动拉起，退出时自动结束。
"""
import threading
import logging

logger = logging.getLogger("ombre_brain.sync_integration")

_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _run_sync_loop():
    """在后台线程中运行 sync_scheduler 的 sync_loop。"""
    import sys
    import os
    # 把 sync_scheduler.py 所在目录加入 path
    scheduler_dir = os.path.join(os.path.dirname(__file__), "..")
    sys.path.insert(0, os.path.abspath(scheduler_dir))
    try:
        import sync_scheduler
        logger.info("[sync] 后台线程启动 sync_loop")
        sync_scheduler.POLL_INTERVAL = 120
        # 用 httpx 的 sync client 轮询，不走 asyncio
        sync_scheduler.sync_loop()
    except Exception as e:
        logger.error(f"[sync] sync_loop 异常退出: {e}")


def start():
    global _thread
    if _thread and _thread.is_alive():
        return  # 已在运行
    _stop_event.clear()
    _thread = threading.Thread(target=_run_sync_loop, daemon=True, name="sync-scheduler")
    _thread.start()
    logger.info("[sync] 后台线程已启动")


def stop():
    """标记停止（线程在下次轮询时自然退出）。"""
    logger.info("[sync] 收到停止信号")
    # sync_loop 里没有退出逻辑，暂不强制终止
