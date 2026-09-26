from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_facebook_url(raw_url: str) -> str:
    """
    Normalizes a Facebook Page URL into a consistent canonical form:
    - Lowercases scheme and netloc (standardizing to www.facebook.com)
    - Strips query tracking parameters (mibextid, ref, __cft__, etc.)
    - Removes trailing slashes
    """
    clean = raw_url.strip()
    if not clean:
        return ""

    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean

    parsed = urlparse(clean)
    netloc = parsed.netloc.lower()

    # Standardize Facebook hostnames
    if any(
        h in netloc for h in ["m.facebook.com", "mobile.facebook.com", "web.facebook.com", "fb.com"]
    ):
        netloc = "www.facebook.com"
    elif netloc == "facebook.com":
        netloc = "www.facebook.com"

    # Normalize path: remove trailing slash, handle profile.php?id=...
    path = parsed.path.rstrip("/")
    if not path:
        path = ""

    # Keep only essential query parameters (e.g., id for profile.php)
    tracking_params = {
        "mibextid",
        "ref",
        "__cft__",
        "__tn__",
        "fref",
        "paipv",
        "eav",
        "locale",
        "_rdr",
    }
    filtered_query = []
    if parsed.query:
        for k, v in parse_qsl(parsed.query):
            if k.lower() not in tracking_params:
                filtered_query.append((k, v))

    scheme = parsed.scheme or "https"
    if any(h in netloc for h in ["facebook.com", "fb.com"]):
        scheme = "https"
    elif any(h in netloc for h in ["localhost", "127.0.0.1", "backend"]) or "/mock/" in path:
        scheme = parsed.scheme or "http"

    query_str = urlencode(filtered_query) if filtered_query else ""

    canonical = urlunparse(
        (
            scheme,
            netloc,
            path,
            "",
            query_str,
            "",
        )
    )
    return canonical


class UrlNormalizer:
    @staticmethod
    def normalize(raw_url: str) -> str:
        return normalize_facebook_url(raw_url)
