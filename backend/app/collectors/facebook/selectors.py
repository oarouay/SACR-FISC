"""
Deterministic Facebook DOM selectors.

Selector Hierarchy strictly observed:
1. role
2. label
3. visible text
4. stable attributes
5. CSS selector only when necessary

Avoid:
- generated class names (e.g. .x1i10hfl, .xjb270e)
- deeply nested CSS selectors
- long XPath expressions
"""

# Cookie consent dialogs (multi-language support for common EU/Global dialogs)
COOKIE_CONSENT_BUTTONS = [
    'button:has-text("Allow essential and optional cookies")',
    'button:has-text("Allow all cookies")',
    'button:has-text("Autoriser tous les cookies")',
    'button:has-text("Accepter tout")',
    'button:has-text("Accept all")',
    'button:has-text("Tout accepter")',
    'button:has-text("السماح بكل ملفات تعريف الارتباط")',
    'div[aria-label="Decline optional cookies"]',
    'div[role="dialog"] button:first-of-type',
]

# Close login wall / interstitial modals
LOGIN_CLOSE_BUTTONS = [
    'div[aria-label="Close"]',
    'div[aria-label="Fermer"]',
    'div[aria-label="إغلاق"]',
    'div[role="dialog"] div[aria-label*="lose"]',
]

# Page Identity & Header elements
PAGE_TITLE_SELECTORS = [
    'h1[dir="auto"]',
    "h1",
    'meta[property="og:title"]',
]

PAGE_DESCRIPTION_SELECTORS = [
    'meta[property="og:description"]',
    'meta[name="description"]',
]

# Feed / Post elements
# Facebook posts inside the main feed container are marked with role="article"
FEED_CONTAINER_SELECTORS = [
    'div[role="feed"]',
    'div[role="main"]',
]

POST_ARTICLE_SELECTOR = (
    'div[role="article"], div.rounded-xl:has(button:has-text("Like")), '
    'div.rounded-xl:has(button:has-text("Comment"))'
)

# "See more" / "Afficher la suite" buttons inside post body
POST_SEE_MORE_SELECTORS = [
    'div[role="button"]:has-text("See more")',
    'div[role="button"]:has-text("Afficher la suite")',
    'div[role="button"]:has-text("عرض المزيد")',
]

# Contact info inside About / Intro section
# TODO: On specific Facebook page layouts, inspect custom About tabs if tabs are separated into sub-routes (/about)
CONTACT_SECTION_SELECTORS = [
    'div:has-text("Intro")',
    'div:has-text("À propos")',
    'div:has-text("حول")',
]
