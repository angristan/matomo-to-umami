"""Field mappings between Matomo and Umami schemas."""

import uuid
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

# Matomo URL prefix mapping
URL_PREFIXES: Final[dict[int, str]] = {
    0: "",  # Legacy - domain included in name, no protocol
    1: "http://",
    2: "https://",
    3: "https://www.",
}

# Matomo action types
ACTION_TYPE_URL: Final[int] = 1
ACTION_TYPE_OUTLINK: Final[int] = 2
ACTION_TYPE_DOWNLOAD: Final[int] = 3
ACTION_TYPE_PAGE_TITLE: Final[int] = 4
ACTION_TYPE_ECOMMERCE_ITEM_SKU: Final[int] = 5
ACTION_TYPE_ECOMMERCE_ITEM_NAME: Final[int] = 6
ACTION_TYPE_ECOMMERCE_ITEM_CATEGORY: Final[int] = 7
ACTION_TYPE_SITE_SEARCH: Final[int] = 8
ACTION_TYPE_EVENT_CATEGORY: Final[int] = 10
ACTION_TYPE_EVENT_ACTION: Final[int] = 11
ACTION_TYPE_EVENT_NAME: Final[int] = 12
ACTION_TYPE_CONTENT_NAME: Final[int] = 13
ACTION_TYPE_CONTENT_PIECE: Final[int] = 14
ACTION_TYPE_CONTENT_TARGET: Final[int] = 15
ACTION_TYPE_CONTENT_INTERACTION: Final[int] = 16

# Matomo device type mapping to Umami device names
# Umami only has: desktop, laptop, mobile, tablet, unknown
DEVICE_TYPES: Final[dict[int, str]] = {
    0: "desktop",
    1: "mobile",  # smartphone
    2: "tablet",
    3: "mobile",  # feature phone
    4: "desktop",  # console
    5: "desktop",  # tv
    6: "desktop",  # car browser
    7: "desktop",  # smart display
    8: "desktop",  # camera
    9: "mobile",  # portable media player
    10: "mobile",  # phablet
    11: "desktop",  # smart speaker
    12: "mobile",  # wearable
    13: "desktop",  # peripheral
}

# Matomo browser codes to Umami browser names
# Reference: https://github.com/matomo-org/device-detector
# Only browsers with icons in Umami (public/images/browser/) are mapped
# Unrecognized browsers will be mapped to "unknown"
BROWSER_MAPPING: Final[dict[str, str]] = {
    # Major browsers
    "CH": "chrome",
    "CR": "chrome",  # Chromium
    "FF": "firefox",
    "SF": "safari",
    "IE": "ie",
    "ED": "edge",
    "OP": "opera",
    # Mobile variants (map to base browser or specific mobile icon)
    "CM": "chrome",  # Chrome Mobile
    "CI": "crios",  # Chrome iOS
    "FM": "firefox",  # Firefox Mobile
    "MF": "firefox",  # Firefox Mobile
    "FI": "fxios",  # Firefox iOS
    "SM": "safari",  # Safari Mobile
    "AN": "android",  # Android Browser
    "SB": "samsung",  # Samsung Browser
    "MI": "miui",  # MIUI Browser
    # Firefox-based browsers (map to firefox)
    "PS": "firefox",  # Pale Moon
    "F1": "firefox",  # Firefox Focus
    "FK": "firefox",  # Firefox Klar
    "WA": "firefox",  # Waterfox
    "LB": "firefox",  # LibreWolf
    "FL": "firefox",  # Floorp
    "TH": "firefox",  # Tor Browser
    # Chromium-based browsers (map to chrome)
    "VI": "chrome",  # Vivaldi
    "AR": "chrome",  # Arc
    "DU": "chrome",  # DuckDuckGo
    "CC": "chrome",  # Coc Coc
    "CO": "chrome",  # CoolNovo
    "IR": "chrome",  # Iron
    "CD": "chrome",  # Comodo Dragon
    "UR": "chrome",  # Ur Browser
    "WH": "chrome",  # Whale
    # Opera-based browsers (also Chromium-based)
    "OM": "opera",  # Opera Mobile
    # Alternative browsers (only those with Umami icons)
    "BR": "brave",
    "YA": "yandexbrowser",
    "OI": "opera-mini",
    "SI": "silk",  # Amazon Silk
    "BB": "blackberry",
    "AO": "aol",
    "KT": "kakaotalk",
    "CU": "curl",
    # WebViews and embedded
    "CW": "chromium-webview",
    "CV": "chromium-webview",
    "WV": "android-webview",
    "AW": "android-webview",
    "IW": "ios-webview",
    "FB": "facebook",
    "IG": "instagram",
    # Headless/Automation (map to base browser)
    "HC": "chrome",  # Headless Chrome
    "PP": "chrome",  # Puppeteer (uses Chromium)
    # Edge variants
    "EI": "edge-ios",
    "EC": "edge-chromium",
}

# Matomo OS codes to Umami OS names
# Reference: https://github.com/matomo-org/device-detector
# Umami has icons for: windows, mac-os, linux, chrome-os, android, ios,
# blackberry-os, windows-mobile, open-bsd, unknown
OS_MAPPING: Final[dict[str, str]] = {
    # Desktop OS
    "WIN": "windows",
    "WI7": "windows",  # Windows 7
    "W81": "windows",  # Windows 8.1
    "W10": "windows",  # Windows 10
    "WI1": "windows",  # Windows 11
    "MAC": "mac-os",
    "LIN": "linux",
    "COS": "chrome-os",
    # Mobile OS
    "AND": "android",
    "IOS": "ios",
    "IPA": "ios",  # iPad
    "IPH": "ios",  # iPhone
    "WPH": "windows-mobile",
    "WMO": "windows-mobile",
    "WRT": "windows-mobile",  # Windows RT
    "BLB": "blackberry-os",
    "SYM": "linux",  # Symbian - no icon, use unknown
    "WEB": "linux",  # webOS - no icon
    "KAI": "linux",  # KaiOS - no icon
    "HAR": "android",  # HarmonyOS - closest is Android
    "FUC": "linux",  # Fuchsia - no icon
    "FOS": "linux",  # Firefox OS
    # Linux distributions (all map to linux)
    "UBT": "linux",  # Ubuntu
    "FED": "linux",  # Fedora
    "DEB": "linux",  # Debian
    "MIN": "linux",  # Mint
    "ARC": "linux",  # Arch
    "CEN": "linux",  # CentOS
    "RHL": "linux",  # Red Hat
    "SUS": "linux",  # SUSE
    "GEN": "linux",  # Gentoo
    "MAN": "linux",  # Manjaro
    "ELE": "linux",  # Elementary
    "POP": "linux",  # Pop!_OS
    # BSD variants
    "BSD": "linux",  # Generic BSD
    "FRE": "linux",  # FreeBSD
    "OPE": "open-bsd",  # OpenBSD
    "NET": "linux",  # NetBSD
    # Gaming consoles
    "PS3": "unknown",  # PlayStation 3
    "PS4": "unknown",  # PlayStation 4
    "PS5": "unknown",  # PlayStation 5
    "XB1": "unknown",  # Xbox One
    "XBX": "unknown",  # Xbox
    "WII": "unknown",  # Wii
    "NDS": "unknown",  # Nintendo DS
    # Other
    "AMZ": "android",  # Fire OS - based on Android
    "TIZ": "linux",  # Tizen
    "ROS": "linux",  # Robot OS
    "HAI": "linux",  # Haiku
    "OBS": "linux",  # Other BSD
    "UNK": "unknown",
}


@dataclass
class SiteMapping:
    """Maps a Matomo site to an Umami website."""

    matomo_idsite: int
    umami_website_id: str
    domain: str


def generate_uuid_from_matomo_id(matomo_id: int, prefix: str) -> str:
    """Generate a deterministic UUID from a Matomo integer ID.

    Uses UUID v5 with a namespace to ensure consistent mapping.
    """
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace
    name = f"matomo:{prefix}:{matomo_id}"
    return str(uuid.uuid5(namespace, name))


def parse_matomo_url(name: str, url_prefix: int | None) -> tuple[str, str, str | None]:
    """Parse Matomo URL into hostname, path, and query string.

    Returns (hostname, path, query) tuple.
    """
    if url_prefix is None:
        url_prefix = 0

    prefix = URL_PREFIXES.get(url_prefix, "")

    # Reconstruct full URL for parsing
    # Prefix 0 means domain is in name without protocol
    # BUT outlinks/downloads store full URL with protocol in name (prefix NULL/0)
    if url_prefix == 0:
        # Check if name already has a protocol
        if name.startswith(("http://", "https://")):
            full_url = name
        else:
            full_url = "https://" + name
    else:
        full_url = prefix + name

    parsed = urlparse(full_url)
    hostname = parsed.netloc or ""
    path = parsed.path or "/"
    query = parsed.query or None

    return hostname, path, query


def parse_referrer_url(
    referer_url: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Parse referrer URL into domain, path, and query string.

    Returns (referrer_domain, referrer_path, referrer_query) tuple.
    """
    if not referer_url:
        return None, None, None

    # Add protocol if missing for urlparse to work correctly
    if "://" not in referer_url:
        referer_url = "https://" + referer_url

    parsed = urlparse(referer_url)
    domain = parsed.netloc or None
    # Strip www. prefix to match Umami's normalization
    if domain and domain.startswith("www."):
        domain = domain[4:]
    path = parsed.path or "/"
    query = parsed.query or None

    return domain, path, query


def map_browser(matomo_code: str | None) -> str | None:
    """Map Matomo browser code to Umami browser name.

    Only returns browser names that Umami recognizes (has icons for).
    Unrecognized browsers are mapped to "unknown".
    """
    if not matomo_code:
        return None
    return BROWSER_MAPPING.get(matomo_code, "unknown")


def map_os(matomo_code: str | None) -> str | None:
    """Map Matomo OS code to Umami OS name.

    Only returns OS names that Umami recognizes (has icons for).
    Unrecognized OS codes are mapped to "unknown".
    """
    if not matomo_code:
        return None
    return OS_MAPPING.get(matomo_code, "unknown")


def map_device_type(matomo_type: int | None) -> str | None:
    """Map Matomo device type to Umami device name."""
    if matomo_type is None:
        return None
    return DEVICE_TYPES.get(matomo_type, "desktop")


def truncate_field(value: str | None, max_length: int) -> str | None:
    """Truncate a field to max length for Umami schema compatibility."""
    if value is None:
        return None
    return value[:max_length] if len(value) > max_length else value
