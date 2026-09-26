import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Browser, async_playwright

from app.collectors.base import (
    BaseCollector,
    CrawlResult,
    EvidenceArtifact,
    RawPageMetadata,
    RawPostData,
)
from app.collectors.facebook.adapter import FacebookPageAdapter
from app.collectors.facebook.exceptions import (
    CollectorException,
)
from app.core.config import settings
from app.core.logging import logger
from app.models.crawl_job import CrawlErrorCode, CrawlStatus


class FacebookPageCollector(BaseCollector):
    def __init__(
        self,
        storage_state_path: str | None = None,
        headless: bool = True,
        page_timeout: int = 30000,
        browser: Browser | None = None,
        block_media: bool | None = None,
    ) -> None:
        self.storage_state_path = storage_state_path or settings.FACEBOOK_STORAGE_STATE
        self.headless = headless
        self.page_timeout = page_timeout
        self.collector_version = settings.COLLECTOR_VERSION
        self.browser = browser
        self.block_media = (
            block_media if block_media is not None else settings.BLOCK_MEDIA_ON_QUICK_CRAWL
        )

    def validate_target(self, url: str) -> bool:
        """
        Validates that the URL targets Facebook.
        """
        if not url:
            return False
        try:
            parsed = urlparse(url.strip())
            if parsed.scheme not in ("http", "https"):
                return False
            netloc = parsed.netloc.lower()
            return (
                any(
                    domain in netloc
                    for domain in (
                        "facebook.com",
                        "m.facebook.com",
                        "web.facebook.com",
                        "fb.com",
                        "fb.watch",
                        "localhost",
                        "127.0.0.1",
                        "backend",
                    )
                )
                or "/mock/" in parsed.path
            )
        except Exception:
            return False

    def _validate_storage_state(self) -> Path | None:
        """
        Checks if storage state JSON file exists and is valid JSON without logging sensitive data.
        """
        if not self.storage_state_path:
            return None

        path = Path(self.storage_state_path)
        if not path.is_file():
            logger.info(
                "Provided storage state path does not exist; proceeding with anonymous session."
            )
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict) or "cookies" not in data:
                    logger.warning("Storage state JSON invalid format; ignoring.")
                    return None
            return path
        except Exception as e:
            logger.warning(f"Failed to read storage state file: {e}")
            return None

    async def capture_evidence(
        self, evidence_type: str, metadata: dict[str, Any]
    ) -> EvidenceArtifact | None:
        raise NotImplementedError("Call run() or execute via adapter context")

    async def run(
        self,
        job_id: uuid.UUID,
        target_url: str,
        max_posts: int | None = None,
        max_scroll_cycles: int | None = None,
        crawl_mode: str = "QUICK",
    ) -> CrawlResult:
        """
        Executes deterministic crawl on a controlled Facebook Page.
        Follows bounded scrolling, deduplication, and evidence preservation.
        """
        if not self.validate_target(target_url):
            return CrawlResult(
                status=CrawlStatus.FAILED,
                error_code=CrawlErrorCode.INVALID_URL.value,
                error_message=f"Target URL '{target_url}' is not a recognized Facebook URL.",
            )

        if max_posts is None:
            max_posts = (
                settings.QUICK_POST_LIMIT if crawl_mode == "QUICK" else settings.DEEP_POST_LIMIT
            )
        if max_scroll_cycles is None:
            max_scroll_cycles = (
                settings.QUICK_MAX_SCROLL_CYCLES
                if crawl_mode == "QUICK"
                else settings.DEEP_MAX_SCROLL_CYCLES
            )

        if self.browser:
            return await self._execute_crawl(
                browser=self.browser,
                job_id=job_id,
                target_url=target_url,
                max_posts=max_posts,
                max_scroll_cycles=max_scroll_cycles,
                crawl_mode=crawl_mode,
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            try:
                return await self._execute_crawl(
                    browser=browser,
                    job_id=job_id,
                    target_url=target_url,
                    max_posts=max_posts,
                    max_scroll_cycles=max_scroll_cycles,
                    crawl_mode=crawl_mode,
                )
            finally:
                await browser.close()

    async def _execute_crawl(
        self,
        browser: Browser,
        job_id: uuid.UUID,
        target_url: str,
        max_posts: int,
        max_scroll_cycles: int,
        crawl_mode: str = "QUICK",
    ) -> CrawlResult:
        storage_path = self._validate_storage_state()
        evidence_items: list[EvidenceArtifact] = []
        collected_posts: list[RawPostData] = []
        seen_post_identifiers: set[str] = set()

        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        }
        if storage_path:
            context_kwargs["storage_state"] = str(storage_path)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        page.set_default_timeout(self.page_timeout)

        # Resource control: skip video/audio on quick crawl
        if crawl_mode == "QUICK" and self.block_media:

            async def _route_filter(route: Any) -> None:
                try:
                    if route.request.resource_type in ["media", "video", "audio"]:
                        await route.abort()
                    else:
                        await route.continue_()
                except Exception:
                    pass

            try:
                await page.route("**/*", _route_filter)
            except Exception:
                pass

        # Translate host localhost:8000 to backend:8000 inside Docker environment
        nav_url = target_url
        if "backend" in settings.DATABASE_URL or "postgres" in settings.DATABASE_URL:
            nav_url = target_url.replace("http://localhost:8000", "http://backend:8000").replace(
                "http://127.0.0.1:8000", "http://backend:8000"
            )

        adapter = FacebookPageAdapter(page)

        try:
            logger.info(f"Navigating to {nav_url} [Job ID: {job_id}]")
            await page.goto(nav_url, wait_until="domcontentloaded", timeout=self.page_timeout)

            await page.wait_for_timeout(2000)

            # Check for blocking states (CAPTCHA, LoginRequired, 404, Restriction)
            await adapter.check_page_state()
            # Dismiss cookie dialogs and close modals
            await adapter.dismiss_banners()

            # 1. Capture Page Overview Evidence Screenshot
            try:
                overview_png = await page.screenshot(full_page=False)
                evidence_items.append(
                    EvidenceArtifact(
                        evidence_type="SCREENSHOT_PAGE",
                        data=overview_png,
                        filename_prefix=f"page_overview_{job_id}",
                        metadata={"url": target_url, "captured_at": datetime.now(UTC).isoformat()},
                    )
                )
            except Exception as e:
                logger.warning(f"Could not capture overview screenshot: {e}")

            # 2. Collect Page Metadata
            page_name = await adapter.get_page_name()
            page_desc = await adapter.get_page_description()
            page_identity = await adapter.get_page_identity()
            page_category = await adapter.get_page_category()
            contacts = await adapter.get_public_contacts()
            website = await adapter.get_website()
            address = await adapter.get_public_address()

            page_metadata = RawPageMetadata(
                name=page_name,
                canonical_url=target_url,
                platform_page_id=page_identity,
                description=page_desc,
                category=page_category,
                public_phone=contacts.get("phone"),
                public_email=contacts.get("email"),
                website=website or contacts.get("website"),
                public_address=address or contacts.get("address"),
                raw_metadata={"detected_url": page.url, "collector": self.collector_version},
            )

            # 3. Collect Posts with Bounded Scrolling and Deduplication
            stagnant_cycles = 0
            scroll_cycles = 0

            while len(collected_posts) < max_posts and scroll_cycles < max_scroll_cycles:
                post_locators = await adapter.get_posts()
                new_posts_found_this_cycle = 0

                for locator in post_locators:
                    if len(collected_posts) >= max_posts:
                        break

                    permalink = await adapter.get_post_permalink(locator)
                    text = await adapter.get_post_text(locator)

                    if not text and not permalink:
                        continue

                    # Deduplicate by platform post ID or permalink
                    post_id_token = adapter.extract_platform_post_id(permalink, text)
                    if post_id_token in seen_post_identifiers:
                        continue

                    seen_post_identifiers.add(post_id_token)
                    new_posts_found_this_cycle += 1

                    # Calculate deterministic content hash
                    content_hash = hashlib.sha256((text or "").encode("utf-8")).hexdigest()

                    raw_post = RawPostData(
                        platform_post_id=post_id_token,
                        permalink=permalink,
                        text=text,
                        published_at=await adapter.get_post_timestamp(locator),
                        raw_data={"adapter_index": len(collected_posts), "permalink": permalink},
                        content_hash=content_hash,
                    )
                    collected_posts.append(raw_post)

                # Bounded scrolling conditions
                if len(collected_posts) >= max_posts:
                    logger.info(f"Target max_posts ({max_posts}) reached.")
                    break

                if new_posts_found_this_cycle == 0:
                    stagnant_cycles += 1
                    if stagnant_cycles >= 3:
                        logger.info(
                            "No new posts appeared after 3 consecutive scrolls. Stopping scroll loop."
                        )
                        break
                else:
                    stagnant_cycles = 0

                scroll_cycles += 1
                if scroll_cycles >= max_scroll_cycles:
                    logger.info(f"Max scroll cycles ({max_scroll_cycles}) reached. Stopping.")
                    break

                # Perform bounded scroll
                await adapter.scroll_down(step=1200)

            # 4. Capture screenshot of first commercial post if any
            if collected_posts:
                try:
                    post_png = await page.screenshot(full_page=False)
                    evidence_items.append(
                        EvidenceArtifact(
                            evidence_type="SCREENSHOT_POST",
                            data=post_png,
                            filename_prefix=f"top_post_{job_id}",
                            metadata={"post_count": len(collected_posts)},
                            post_index=0,
                        )
                    )
                except Exception:
                    pass

            return CrawlResult(
                status=CrawlStatus.SUCCESS if collected_posts else CrawlStatus.PARTIAL,
                posts_collected=len(collected_posts),
                page_metadata=page_metadata,
                posts=collected_posts,
                evidence_items=evidence_items,
            )

        except CollectorException as ce:
            logger.error(f"Collector blocked/failed with code {ce.error_code}: {ce.message}")
            try:
                err_png = await page.screenshot(full_page=False)
                evidence_items.append(
                    EvidenceArtifact(
                        evidence_type="SCREENSHOT_ERROR",
                        data=err_png,
                        filename_prefix=f"error_{job_id}",
                        metadata={"error_code": ce.error_code, "error_message": ce.message},
                    )
                )
            except Exception:
                pass

            return CrawlResult(
                status=CrawlStatus.FAILED,
                posts_collected=len(collected_posts),
                evidence_items=evidence_items,
                error_code=ce.error_code,
                error_message=ce.message,
            )

        except Exception as e:
            logger.exception(f"Unexpected crawler error: {e}")
            error_code = (
                CrawlErrorCode.TIMEOUT.value
                if "timeout" in str(e).lower()
                else CrawlErrorCode.UNKNOWN_ERROR.value
            )
            try:
                err_png = await page.screenshot(full_page=False)
                evidence_items.append(
                    EvidenceArtifact(
                        evidence_type="SCREENSHOT_ERROR",
                        data=err_png,
                        filename_prefix=f"error_{job_id}",
                        metadata={"error_code": error_code, "error_message": str(e)},
                    )
                )
            except Exception:
                pass

            return CrawlResult(
                status=CrawlStatus.FAILED,
                posts_collected=len(collected_posts),
                evidence_items=evidence_items,
                error_code=error_code,
                error_message=str(e),
            )
        finally:
            await context.close()
