import hashlib
import re
from datetime import datetime

from playwright.async_api import Locator, Page

from app.collectors.facebook.exceptions import (
    AccessRestrictedError,
    CaptchaDetectedError,
    LoginRequiredError,
    PageNotFoundError,
)
from app.collectors.facebook.selectors import (
    COOKIE_CONSENT_BUTTONS,
    LOGIN_CLOSE_BUTTONS,
    PAGE_DESCRIPTION_SELECTORS,
    PAGE_TITLE_SELECTORS,
    POST_ARTICLE_SELECTOR,
    POST_SEE_MORE_SELECTORS,
)
from app.core.logging import logger
from app.extraction.emails import EmailExtractor
from app.extraction.phones import PhoneExtractor


class FacebookPageAdapter:
    """
    Encapsulates all Facebook DOM interactions and selectors.
    Strictly adheres to selector hierarchy: role > label > visible text > stable attributes.
    """

    def __init__(self, page: Page) -> None:
        self.page = page

    async def check_page_state(self) -> None:
        """
        Detects blocking states (CAPTCHA, Login Wall, 404, Restriction) before proceeding.
        """
        title = await self.page.title()
        url = self.page.url

        # 1. 404 / Page Not Found
        if "Content not found" in title or "Page Not Found" in title or "Page introuvable" in title:
            raise PageNotFoundError("Facebook page was not found or has been deleted.")

        # 2. CAPTCHA / Security check
        captcha_indicators = ["security check", "checkpoint", "captcha", "confirmez votre identité"]
        if any(term in title.lower() or term in url.lower() for term in captcha_indicators):
            raise CaptchaDetectedError(
                "Facebook presented a CAPTCHA or security verification checkpoint."
            )

        # 3. Access restricted
        restriction_indicators = ["access restricted", "account disabled", "temporarily blocked"]
        if any(term in title.lower() for term in restriction_indicators):
            raise AccessRestrictedError("Access to this Facebook page is restricted.")

        # 4. Strict login wall where page content is blocked
        if "/login" in url and "next=" in url:
            raise LoginRequiredError(
                "Facebook requires authentication to access this page content."
            )

    async def dismiss_banners(self) -> None:
        """
        Dismisses cookie consent popups and login dialog banners if present.
        """
        # Dismiss cookie consents
        for selector in COOKIE_CONSENT_BUTTONS:
            try:
                locator = self.page.locator(selector).first
                if await locator.is_visible(timeout=1000):
                    await locator.click()
                    await self.page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        # Dismiss login close / dismiss modal
        for selector in LOGIN_CLOSE_BUTTONS:
            try:
                locator = self.page.locator(selector).first
                if await locator.is_visible(timeout=1000):
                    await locator.click()
                    await self.page.wait_for_timeout(500)
                    break
            except Exception:
                continue

    async def get_page_name(self) -> str:
        """
        Extracts the official name of the Facebook page.
        """
        # Try og:title first
        try:
            og_loc = self.page.locator('meta[property="og:title"]')
            if await og_loc.count() > 0:
                og_title = await og_loc.first.get_attribute("content", timeout=300)
                if og_title and "|" in og_title:
                    return og_title.split("|")[0].strip()
                if og_title:
                    return og_title.strip()
        except Exception:
            pass

        # Try page heading
        for sel in PAGE_TITLE_SELECTORS:
            try:
                loc = self.page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    txt = await loc.inner_text()
                    if txt and txt.strip():
                        return txt.strip()
            except Exception:
                continue

        # Fallback to document title
        doc_title = await self.page.title()
        if doc_title:
            return doc_title.split("|")[0].split("- Facebook")[0].strip()

        return "Unknown Facebook Page"

    async def get_page_description(self) -> str | None:
        """
        Extracts page description from meta tags or intro section.
        """
        for sel in PAGE_DESCRIPTION_SELECTORS:
            try:
                loc = self.page.locator(sel)
                if await loc.count() > 0:
                    desc = await loc.first.get_attribute("content", timeout=300)
                    if desc and desc.strip():
                        return desc.strip()
            except Exception:
                continue

        # Check intro bio text if present in page intro
        try:
            bio_loc = self.page.locator("i.fa-align-left ~ b, i.fa-align-left + b").first
            if await bio_loc.is_visible(timeout=300):
                txt = await bio_loc.inner_text()
                if txt and txt.strip():
                    return txt.strip()
        except Exception:
            pass

        return None

    async def get_page_identity(self) -> str | None:
        """
        Extracts stable username or page ID from URL or page metadata.
        """
        url = self.page.url

        # Match /mock/<id>.html
        mock_match = re.search(r"/mock/(\d+)\.html", url)
        if mock_match:
            return mock_match.group(1)

        # Match facebook.com/<username_or_id>
        match = re.search(r"facebook\.com/([^/?#]+)", url)
        if match and match.group(1) not in ("pages", "profile.php", "groups"):
            return match.group(1)

        # Match profile.php?id=<id>
        id_match = re.search(r"id=(\d+)", url)
        if id_match:
            return id_match.group(1)

        return None

    async def get_page_category(self) -> str | None:
        """
        Extracts business or page category if labeled.
        """
        try:
            meta_tag_loc = self.page.locator('meta[name="category"]')
            if await meta_tag_loc.count() > 0:
                meta_tag = await meta_tag_loc.first.get_attribute("content", timeout=300)
                if meta_tag:
                    return meta_tag.strip()
        except Exception:
            pass

        # Check page intro category: "Page · <b>...</b>"
        try:
            cat_loc = self.page.locator("i.fa-info-circle ~ b, i.fa-info-circle + b").first
            if await cat_loc.is_visible(timeout=300):
                txt = await cat_loc.inner_text()
                if txt and txt.strip():
                    return txt.strip()
        except Exception:
            pass

        return None

    async def get_public_contacts(self) -> dict[str, str | None]:
        """
        Gathers public contact details (phone, email, website, address) from intro and visible text.
        """
        contacts: dict[str, str | None] = {
            "phone": None,
            "email": None,
            "website": None,
            "address": None,
        }

        try:
            # Look at all mailto: links
            email_link = self.page.locator('a[href^="mailto:"]')
            if await email_link.count() > 0:
                href = await email_link.first.get_attribute("href", timeout=300)
                if href:
                    contacts["email"] = href.replace("mailto:", "").split("?")[0].strip()

            # Look at tel: links
            tel_link = self.page.locator('a[href^="tel:"]')
            if await tel_link.count() > 0:
                href = await tel_link.first.get_attribute("href", timeout=300)
                if href:
                    contacts["phone"] = href.replace("tel:", "").strip()

            # If not found via link attributes, search in the page text
            page_text = await self.page.inner_text("body")
            if not contacts["phone"]:
                phone_signals = PhoneExtractor.extract(page_text[:4000])
                if phone_signals:
                    contacts["phone"] = phone_signals[0]["normalized_value"]

            if not contacts["email"]:
                email_signals = EmailExtractor.extract(page_text[:4000])
                if email_signals:
                    contacts["email"] = email_signals[0]["normalized_value"]
        except Exception as e:
            logger.debug(f"Non-critical contact extraction error: {e}")

        return contacts

    async def get_website(self) -> str | None:
        """
        Extracts external website link displayed in page intro.
        """
        try:
            link_loc = self.page.locator("i.fa-link ~ a, i.fa-link ~ b").first
            if await link_loc.is_visible(timeout=300):
                txt = await link_loc.inner_text()
                if txt and txt.strip():
                    return txt.strip()
        except Exception:
            pass

        try:
            # Look for external links that are not facebook.com
            external_links = self.page.locator('div[role="main"] a[target="_blank"]')
            count = await external_links.count()
            for i in range(min(count, 5)):
                href = await external_links.nth(i).get_attribute("href", timeout=300)
                if href and "facebook.com" not in href and "fb.com" not in href:
                    return href
        except Exception:
            pass
        return None

    async def get_public_address(self) -> str | None:
        """
        Extracts public address if displayed in intro.
        """
        # TODO: Add dedicated address locator when inspecting specific controlled Facebook page layout
        return None

    async def get_posts(self) -> list[Locator]:
        """
        Returns list of Locators for all posts currently rendered in the feed.
        """
        posts_loc = self.page.locator(POST_ARTICLE_SELECTOR)
        count = await posts_loc.count()
        return [posts_loc.nth(i) for i in range(count)]

    async def get_post_text(self, post_locator: Locator) -> str | None:
        """
        Extracts visible text of a post, expanding truncated 'See more' text if present.
        """
        # Attempt to expand "See more"
        for btn_sel in POST_SEE_MORE_SELECTORS:
            try:
                see_more_btn = post_locator.locator(btn_sel).first
                if await see_more_btn.is_visible(timeout=200):
                    await see_more_btn.click()
                    await self.page.wait_for_timeout(100)
            except Exception:
                pass

        try:
            raw_text = await post_locator.inner_text()
            return raw_text.strip() if raw_text else None
        except Exception:
            return None

    async def get_post_permalink(self, post_locator: Locator) -> str | None:
        """
        Extracts the permalink URL of a post from its timestamp anchor or link element.
        """
        try:
            # Facebook post permalinks typically reside on the timestamp link
            links = post_locator.locator("a")
            count = await links.count()
            for i in range(min(count, 5)):
                href = await links.nth(i).get_attribute("href", timeout=300)
                if href and (
                    "/posts/" in href
                    or "/photos/" in href
                    or "/permalink/" in href
                    or "fbid=" in href
                    or "/videos/" in href
                ):
                    clean_url = href.split("?")[0] if "fbid=" not in href else href
                    if clean_url.startswith("/"):
                        clean_url = f"https://www.facebook.com{clean_url}"
                    return clean_url
        except Exception:
            pass
        return None

    @staticmethod
    def extract_platform_post_id(permalink: str | None, text: str | None) -> str:
        """
        Extracts or computes a stable identifier for post deduplication.
        Priority:
        1. Numerical ID in permalink (/posts/123456789 or fbid=123456789)
        2. Clean permalink
        3. Deterministic SHA-256 content hash of the text
        """
        if permalink:
            match = re.search(r"/(?:posts|photos|permalink|videos)/([a-zA-Z0-9_-]+)", permalink)
            if match:
                return match.group(1)
            id_match = re.search(r"(?:fbid|id)=(\d+)", permalink)
            if id_match:
                return id_match.group(1)
            return permalink

        # Fallback to hash of text if no permalink available
        safe_text = text or ""
        return f"gen_{hashlib.sha256(safe_text.encode('utf-8')).hexdigest()[:20]}"

    async def get_post_timestamp(self, post_locator: Locator) -> datetime | None:
        """
        Extracts published timestamp from post element if available.
        """
        # TODO: Detailed timestamp parsing from hover tooltip or abbr element on controlled page
        return None

    async def scroll_down(self, step: int = 1000) -> None:
        """
        Performs bounded, controlled downward scroll to trigger infinite feed loading.
        """
        await self.page.evaluate(f"window.scrollBy(0, {step});")
        await self.page.wait_for_timeout(1500)
