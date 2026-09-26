import asyncio
import signal
from typing import Any

from playwright.async_api import Browser, Playwright, async_playwright

from app.core.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.crawl_target import CrawlTarget
from app.queue.target_queue import target_queue
from app.services.crawl_service import crawl_service


class CrawlerWorker:
    def __init__(self, concurrency: int | None = None) -> None:
        self.concurrency = concurrency or settings.CRAWLER_CONCURRENCY
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.is_running = True
        self.active_tasks: set[asyncio.Task[Any]] = set()

    async def _safe_process(self, target: CrawlTarget, browser: Browser) -> None:
        async with self.semaphore:
            try:
                logger.info(
                    f"Processing target {target.id} ({target.canonical_url}) in mode {target.crawl_mode}"
                )
                await crawl_service.process_target(target, browser=browser)
            except Exception as e:
                logger.exception(f"Unhandled error processing target {target.id}: {e}")
                async with AsyncSessionLocal() as session:
                    await target_queue.schedule_retry(
                        session, target.id, error_code="WORKER_EXCEPTION", error_message=str(e)
                    )

    async def run(self) -> None:
        logger.info(
            f"Starting Autonomous Crawler Worker (concurrency={self.concurrency}, "
            f"poll_interval={settings.WORKER_POLL_INTERVAL}s)"
        )

        p: Playwright | None = None
        browser: Browser | None = None

        try:
            p = await async_playwright().start()
            browser = await p.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            logger.info("Persistent Playwright browser initialized for worker.")

            while self.is_running:
                # Clean up completed tasks
                self.active_tasks = {t for t in self.active_tasks if not t.done()}

                if len(self.active_tasks) >= self.concurrency:
                    await asyncio.sleep(0.5)
                    continue

                async with AsyncSessionLocal() as session:
                    target = await target_queue.claim_next_target(session)

                if target is None:
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
                    continue

                task = asyncio.create_task(self._safe_process(target, browser))
                self.active_tasks.add(task)

        except asyncio.CancelledError:
            logger.info("Crawler worker loop cancelled.")
        finally:
            logger.info("Shutting down worker. Waiting for active tasks to finish...")
            if self.active_tasks:
                await asyncio.gather(*self.active_tasks, return_exceptions=True)

            if browser:
                await browser.close()
            if p:
                await p.stop()
            logger.info("Crawler worker shutdown complete.")

    def stop(self) -> None:
        logger.info("Stop signal received. Gracefully terminating worker loop...")
        self.is_running = False


async def main() -> None:
    worker = CrawlerWorker()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except (NotImplementedError, RuntimeError):
            # Windows may not support add_signal_handler for some signals
            pass

    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker terminated.")
