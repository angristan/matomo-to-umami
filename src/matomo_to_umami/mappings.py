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
# Umami uses detect-browser which returns values like "Windows 10", "Android OS", etc.
# These get converted to image paths: "Windows 10" -> windows-10.png
OS_MAPPING: Final[dict[str, str]] = {
    # Desktop OS - Windows variants
    "WIN": "Windows 10",
    "WI7": "Windows 7",
    "W81": "Windows 8.1",
    "W10": "Windows 10",
    "WI1": "Windows 10",  # Windows 11 uses Windows 10 icon
    "WXP": "Windows XP",
    "WVI": "Windows Vista",
    "WME": "Windows ME",
    "W98": "Windows 98",
    "W95": "Windows 95",
    "W2K": "Windows 2000",
    "W31": "Windows 3.11",
    "WS3": "Windows Server 2003",
    # Other desktop OS
    "MAC": "Mac OS",
    "LIN": "Linux",
    "COS": "Chrome OS",
    # Mobile OS
    "AND": "Android OS",
    "IOS": "iOS",
    "IPA": "iOS",  # iPad
    "IPH": "iOS",  # iPhone
    "WPH": "Windows Mobile",
    "WMO": "Windows Mobile",
    "WRT": "Windows Mobile",  # Windows RT
    "WCE": "Windows CE",
    "BLB": "BlackBerry OS",
    "SYM": "Linux",  # Symbian - no icon
    "WEB": "Linux",  # webOS - no icon
    "KAI": "Linux",  # KaiOS - no icon
    "HAR": "Android OS",  # HarmonyOS - closest is Android
    "FUC": "Linux",  # Fuchsia - no icon
    "FOS": "Linux",  # Firefox OS
    # Linux distributions (all map to Linux)
    "UBT": "Linux",  # Ubuntu
    "FED": "Linux",  # Fedora
    "DEB": "Linux",  # Debian
    "MIN": "Linux",  # Mint
    "ARC": "Linux",  # Arch
    "CEN": "Linux",  # CentOS
    "RHL": "Linux",  # Red Hat
    "SUS": "Linux",  # SUSE
    "GEN": "Linux",  # Gentoo
    "MAN": "Linux",  # Manjaro
    "ELE": "Linux",  # Elementary
    "POP": "Linux",  # Pop!_OS
    # BSD variants
    "BSD": "Linux",  # Generic BSD
    "FRE": "Linux",  # FreeBSD
    "OPE": "Open BSD",  # OpenBSD
    "NET": "Linux",  # NetBSD
    # Gaming consoles
    "PS3": "Linux",  # PlayStation 3
    "PS4": "Linux",  # PlayStation 4
    "PS5": "Linux",  # PlayStation 5
    "XB1": "Linux",  # Xbox One
    "XBX": "Linux",  # Xbox
    "WII": "Linux",  # Wii
    "NDS": "Linux",  # Nintendo DS
    # Other
    "AMZ": "Amazon OS",  # Fire OS
    "TIZ": "Linux",  # Tizen
    "ROS": "Linux",  # Robot OS
    "HAI": "Linux",  # Haiku
    "OBS": "Linux",  # Other BSD
    "SOS": "Sun OS",
    "QNX": "QNX",
    "BEO": "BeOS",
    "OS2": "OS/2",
    "UNK": "Linux",  # Unknown defaults to Linux (shows icon)
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

    Returns OS names matching detect-browser format (e.g., "Windows 10", "Android OS").
    Unrecognized OS codes default to "Linux" (has icon).
    """
    if not matomo_code:
        return None
    return OS_MAPPING.get(matomo_code, "Linux")


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
