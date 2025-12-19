"""Field mappings between Matomo and Umami schemas."""

from dataclasses import dataclass
from typing import Optional
import hashlib
import uuid


# Matomo URL prefix mapping
URL_PREFIXES = {
    0: "",        # Legacy - domain included in name, no protocol
    1: "http://",
    2: "https://",
    3: "https://www.",
}

# Matomo action types
ACTION_TYPE_URL = 1
ACTION_TYPE_OUTLINK = 2
ACTION_TYPE_DOWNLOAD = 3
ACTION_TYPE_PAGE_TITLE = 4
ACTION_TYPE_ECOMMERCE_ITEM_SKU = 5
ACTION_TYPE_ECOMMERCE_ITEM_NAME = 6
ACTION_TYPE_ECOMMERCE_ITEM_CATEGORY = 7
ACTION_TYPE_SITE_SEARCH = 8
ACTION_TYPE_EVENT_CATEGORY = 10
ACTION_TYPE_EVENT_ACTION = 11
ACTION_TYPE_EVENT_NAME = 12
ACTION_TYPE_CONTENT_NAME = 13
ACTION_TYPE_CONTENT_PIECE = 14
ACTION_TYPE_CONTENT_TARGET = 15
ACTION_TYPE_CONTENT_INTERACTION = 16

# Matomo device type mapping
DEVICE_TYPES = {
    0: "desktop",
    1: "smartphone", 
    2: "tablet",
    3: "feature phone",
    4: "console",
    5: "tv",
    6: "car browser",
    7: "smart display",
    8: "camera",
    9: "portable media player",
    10: "phablet",
    11: "smart speaker",
    12: "wearable",
    13: "peripheral",
}

# Matomo browser codes to Umami browser names
BROWSER_MAPPING = {
    "CH": "chrome",
    "FF": "firefox",
    "SF": "safari",
    "IE": "ie",
    "ED": "edge",
    "OP": "opera",
    "CM": "chrome-mobile",
    "AN": "android-browser",
    "SM": "samsung-browser",
    "UC": "uc-browser",
    "HC": "headless-chrome",
    "CW": "chrome-webview",
}

# Matomo OS codes to Umami OS names
OS_MAPPING = {
    "WIN": "windows",
    "MAC": "mac-os",
    "LIN": "linux",
    "AND": "android",
    "IOS": "ios",
    "UBT": "ubuntu",
    "FED": "fedora",
    "DEB": "debian",
    "COS": "chrome-os",
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


def parse_matomo_url(name: str, url_prefix: Optional[int]) -> tuple[str, str]:
    """Parse Matomo URL into hostname and path.
    
    Returns (hostname, path) tuple.
    """
    if url_prefix is None:
        url_prefix = 0
    
    prefix = URL_PREFIXES.get(url_prefix, "")
    
    # For prefix 0, the domain is included in the name
    if url_prefix == 0:
        if "/" in name:
            hostname, path = name.split("/", 1)
            path = "/" + path
        else:
            hostname = name
            path = "/"
    else:
        # Full URL with prefix
        full_url = prefix + name
        # Parse out hostname and path
        if "://" in full_url:
            without_proto = full_url.split("://", 1)[1]
        else:
            without_proto = full_url
        
        if "/" in without_proto:
            hostname, path = without_proto.split("/", 1)
            path = "/" + path
        else:
            hostname = without_proto
            path = "/"
    
    return hostname, path


def parse_referrer_url(referer_url: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Parse referrer URL into domain and path.
    
    Returns (referrer_domain, referrer_path) tuple.
    """
    if not referer_url:
        return None, None
    
    # Remove protocol
    if "://" in referer_url:
        without_proto = referer_url.split("://", 1)[1]
    else:
        without_proto = referer_url
    
    # Split domain and path
    if "/" in without_proto:
        domain, path = without_proto.split("/", 1)
        path = "/" + path
    else:
        domain = without_proto
        path = "/"
    
    return domain, path


def map_browser(matomo_code: Optional[str]) -> Optional[str]:
    """Map Matomo browser code to Umami browser name."""
    if not matomo_code:
        return None
    return BROWSER_MAPPING.get(matomo_code, matomo_code.lower())


def map_os(matomo_code: Optional[str]) -> Optional[str]:
    """Map Matomo OS code to Umami OS name."""
    if not matomo_code:
        return None
    return OS_MAPPING.get(matomo_code, matomo_code.lower())


def map_device_type(matomo_type: Optional[int]) -> Optional[str]:
    """Map Matomo device type to Umami device name."""
    if matomo_type is None:
        return None
    return DEVICE_TYPES.get(matomo_type, "desktop")


def truncate_field(value: Optional[str], max_length: int) -> Optional[str]:
    """Truncate a field to max length for Umami schema compatibility."""
    if value is None:
        return None
    return value[:max_length] if len(value) > max_length else value
