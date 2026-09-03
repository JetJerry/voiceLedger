"""
VoiceLedger Background Worker Entrypoint.

Runs the asynchronous outbox worker to poll pending outbox events from PostgreSQL
and publish them to the Redis event bus.

Usage:
    python -m backend.app.worker
"""
import asyncio
import logging
import signal
import sys

from backend.app.db.session import SessionLocal
from backend.app.core.redis import close_redis_connection
from backend.app.services.outbox_worker import outbox_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voiceledger.worker.main")


async def main() -> None:
    """Worker process main async loop with signal handling."""
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Received termination signal; shutting down outbox worker...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Signal handlers on Windows may not support add_signal_handler
            pass

    logger.info("VoiceLedger background worker process started")
    try:
        await outbox_worker.run_loop(
            db_session_factory=SessionLocal,
            poll_interval_seconds=1.0,
            stop_event=stop_event,
        )
    finally:
        await close_redis_connection()
        logger.info("VoiceLedger background worker process exited cleanly")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
