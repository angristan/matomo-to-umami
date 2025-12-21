"""Tests for field mappings."""

import pytest

from matomo_to_umami.mappings import (
    generate_uuid_from_matomo_id,
    map_browser,
    map_device_type,
    map_os,
    parse_matomo_url,
    parse_referrer_url,
    truncate_field,
)
from matomo_to_umami.migrate import (
    SiteMappingError,
    validate_site_mapping,
)
from matomo_to_umami.region_mappings import convert_region_to_iso


class TestParseMatmoUrl:
    """Tests for parse_matomo_url function."""

    def test_prefix_0_with_path(self):
        """URL prefix 0 includes domain in name."""
        hostname, path, query = parse_matomo_url("stanislas.blog/2019/01/wireguard/", 0)
        assert hostname == "stanislas.blog"
        assert path == "/2019/01/wireguard/"
        assert query is None

    def test_prefix_0_root(self):
        """URL prefix 0 with just domain."""
        hostname, path, query = parse_matomo_url("angristan.fr", 0)
        assert hostname == "angristan.fr"
        assert path == "/"
        assert query is None

    def test_prefix_2_https(self):
        """URL prefix 2 = https://"""
        hostname, path, query = parse_matomo_url("stanislas.blog/path/to/page", 2)
        assert hostname == "stanislas.blog"
        assert path == "/path/to/page"
        assert query is None

    def test_prefix_3_https_www(self):
        """URL prefix 3 = https://www."""
        hostname, path, query = parse_matomo_url("example.com/page", 3)
        assert hostname == "www.example.com"
        assert path == "/page"
        assert query is None

    def test_prefix_none_defaults_to_0(self):
        """None prefix treated as 0."""
        hostname, path, query = parse_matomo_url("example.com/test", None)
        assert hostname == "example.com"
        assert path == "/test"
        assert query is None

    def test_empty_query_string(self):
        """Empty query string after ? returns None."""
        hostname, path, query = parse_matomo_url("example.com/page?", 0)
        assert hostname == "example.com"
        assert path == "/page"
        assert query is None


class TestParseReferrerUrl:
    """Tests for parse_referrer_url function."""

    def test_full_url_with_query(self):
        hostname, path, query = parse_referrer_url(
            "https://www.google.com/search?q=test"
        )
        assert hostname == "google.com"  # www. stripped to match Umami
        assert path == "/search"
        assert query == "q=test"

    def test_url_without_protocol(self):
        hostname, path, query = parse_referrer_url("google.com/")
        assert hostname == "google.com"
        assert path == "/"
        assert query is None

    def test_none_input(self):
        hostname, path, query = parse_referrer_url(None)
        assert hostname is None
        assert path is None
        assert query is None

    def test_empty_string(self):
        hostname, path, query = parse_referrer_url("")
        assert hostname is None
        assert path is None
        assert query is None


class TestMapBrowser:
    """Tests for browser code mapping."""

    def test_chrome(self):
        assert map_browser("CH") == "chrome"

    def test_firefox(self):
        assert map_browser("FF") == "firefox"

    def test_safari(self):
        assert map_browser("SF") == "safari"

    def test_chrome_mobile(self):
        assert map_browser("CM") == "chrome"  # Maps to base browser

    def test_unknown_browser_returns_unknown(self):
        assert map_browser("XX") == "unknown"

    def test_none(self):
        assert map_browser(None) is None


class TestMapOs:
    """Tests for OS code mapping."""

    def test_windows(self):
        assert map_os("WIN") == "Windows 10"

    def test_macos(self):
        assert map_os("MAC") == "Mac OS"

    def test_linux(self):
        assert map_os("LIN") == "Linux"

    def test_android(self):
        assert map_os("AND") == "Android OS"

    def test_ios(self):
        assert map_os("IOS") == "iOS"

    def test_unknown_os_defaults_to_linux(self):
        assert map_os("XXX") == "Linux"

    def test_none(self):
        assert map_os(None) is None


class TestMapDeviceType:
    """Tests for device type mapping."""

    def test_desktop(self):
        assert map_device_type(0) == "desktop"

    def test_smartphone(self):
        assert map_device_type(1) == "mobile"  # smartphone maps to mobile

    def test_tablet(self):
        assert map_device_type(2) == "tablet"

    def test_unknown_defaults_to_desktop(self):
        assert map_device_type(99) == "desktop"

    def test_none(self):
        assert map_device_type(None) is None


class TestGenerateUuid:
    """Tests for UUID generation."""

    def test_deterministic(self):
        """Same input always produces same output."""
        uuid1 = generate_uuid_from_matomo_id(12345, "visit")
        uuid2 = generate_uuid_from_matomo_id(12345, "visit")
        assert uuid1 == uuid2

    def test_different_ids_different_uuids(self):
        """Different IDs produce different UUIDs."""
        uuid1 = generate_uuid_from_matomo_id(1, "visit")
        uuid2 = generate_uuid_from_matomo_id(2, "visit")
        assert uuid1 != uuid2

    def test_different_prefixes_different_uuids(self):
        """Different prefixes produce different UUIDs."""
        uuid1 = generate_uuid_from_matomo_id(1, "visit")
        uuid2 = generate_uuid_from_matomo_id(1, "action")
        assert uuid1 != uuid2

    def test_valid_uuid_format(self):
        """Output is valid UUID format."""
        uuid_str = generate_uuid_from_matomo_id(1, "test")
        import uuid

        # Should not raise
        uuid.UUID(uuid_str)


class TestTruncateField:
    """Tests for field truncation."""

    def test_no_truncation_needed(self):
        assert truncate_field("short", 10) == "short"

    def test_truncation(self):
        assert truncate_field("this is a long string", 10) == "this is a "

    def test_exact_length(self):
        assert truncate_field("12345", 5) == "12345"

    def test_none_input(self):
        assert truncate_field(None, 10) is None


class TestValidateSiteMapping:
    """Tests for site mapping validation."""

    def test_valid_mapping(self):
        """Valid mapping string parses correctly."""
        mapping = validate_site_mapping(
            "1:550e8400-e29b-41d4-a716-446655440000:example.com"
        )
        assert mapping.matomo_idsite == 1
        assert mapping.umami_website_id == "550e8400-e29b-41d4-a716-446655440000"
        assert mapping.domain == "example.com"

    def test_valid_mapping_with_subdomain(self):
        """Domain can include subdomains."""
        mapping = validate_site_mapping(
            "2:550e8400-e29b-41d4-a716-446655440000:www.example.com"
        )
        assert mapping.domain == "www.example.com"

    def test_invalid_format_too_few_parts(self):
        """Mapping with too few parts raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("1:example.com")
        assert "Invalid site mapping format" in str(excinfo.value)

    def test_invalid_matomo_id_not_integer(self):
        """Non-integer Matomo ID raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping(
                "abc:550e8400-e29b-41d4-a716-446655440000:example.com"
            )
        assert "must be an integer" in str(excinfo.value)

    def test_invalid_matomo_id_zero(self):
        """Zero Matomo ID raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("0:550e8400-e29b-41d4-a716-446655440000:example.com")
        assert "must be a positive integer" in str(excinfo.value)

    def test_invalid_matomo_id_negative(self):
        """Negative Matomo ID raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("-1:550e8400-e29b-41d4-a716-446655440000:example.com")
        assert "must be a positive integer" in str(excinfo.value)

    def test_invalid_uuid_format(self):
        """Invalid UUID format raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("1:not-a-valid-uuid:example.com")
        assert "Invalid Umami UUID" in str(excinfo.value)

    def test_invalid_domain_empty(self):
        """Empty domain raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("1:550e8400-e29b-41d4-a716-446655440000:")
        assert "Invalid domain" in str(excinfo.value)

    def test_invalid_domain_starts_with_dot(self):
        """Domain starting with dot raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("1:550e8400-e29b-41d4-a716-446655440000:.example.com")
        assert "Invalid domain" in str(excinfo.value)


class TestExpandedBrowserMappings:
    """Tests for browser mappings to Umami-recognized browsers."""

    def test_brave(self):
        assert map_browser("BR") == "brave"

    def test_samsung(self):
        assert map_browser("SB") == "samsung"

    def test_opera_mini(self):
        assert map_browser("OI") == "opera-mini"

    def test_facebook(self):
        assert map_browser("FB") == "facebook"

    def test_instagram(self):
        assert map_browser("IG") == "instagram"

    def test_yandex(self):
        assert map_browser("YA") == "yandexbrowser"

    def test_chromium(self):
        assert map_browser("CR") == "chrome"

    def test_chromium_based_browsers(self):
        """Chromium-based browsers map to chrome."""
        assert map_browser("VI") == "chrome"  # Vivaldi
        assert map_browser("AR") == "chrome"  # Arc
        assert map_browser("DU") == "chrome"  # DuckDuckGo

    def test_unrecognized_browsers_return_unknown(self):
        """Browsers not in our mapping return 'unknown'."""
        assert map_browser("XX") == "unknown"  # Unknown code

    def test_firefox_based_browsers(self):
        """Firefox-based browsers map to firefox."""
        assert map_browser("PS") == "firefox"  # Pale Moon
        assert map_browser("F1") == "firefox"  # Firefox Focus
        assert map_browser("TH") == "firefox"  # Tor Browser


class TestExpandedOSMappings:
    """Tests for OS mappings to Umami detect-browser format."""

    def test_linux_distros_map_to_linux(self):
        """Linux distributions all map to Linux."""
        assert map_os("UBT") == "Linux"  # Ubuntu
        assert map_os("FED") == "Linux"  # Fedora
        assert map_os("ARC") == "Linux"  # Arch
        assert map_os("POP") == "Linux"  # Pop!_OS

    def test_bsd_variants(self):
        """BSD variants map appropriately."""
        assert map_os("FRE") == "Linux"  # FreeBSD
        assert map_os("OPE") == "Open BSD"  # OpenBSD

    def test_harmonyos(self):
        """HarmonyOS maps to Android OS (closest match)."""
        assert map_os("HAR") == "Android OS"

    def test_windows_variants(self):
        """Windows versions map to specific versions."""
        assert map_os("WI7") == "Windows 7"
        assert map_os("W81") == "Windows 8.1"
        assert map_os("W10") == "Windows 10"

    def test_ios_variants(self):
        """iOS device types all map to iOS."""
        assert map_os("IPA") == "iOS"  # iPad
        assert map_os("IPH") == "iOS"  # iPhone


class TestRegionMapping:
    """Tests for FIPS to ISO 3166-2 region code conversion."""

    def test_france_ile_de_france(self):
        """French FIPS A8 converts to ISO IDF (Île-de-France)."""
        assert convert_region_to_iso("FR", "A8") == "IDF"

    def test_france_rhone_alpes(self):
        """French FIPS B9 converts to merged region ARA."""
        assert convert_region_to_iso("FR", "B9") == "ARA"

    def test_germany_berlin(self):
        """German FIPS 16 converts to ISO BE (Berlin)."""
        assert convert_region_to_iso("DE", "16") == "BE"

    def test_china_guangdong(self):
        """Chinese FIPS 30 converts to ISO GD (Guangdong)."""
        assert convert_region_to_iso("CN", "30") == "GD"

    def test_spain_madrid(self):
        """Spanish FIPS 63 converts to ISO MD (Madrid)."""
        assert convert_region_to_iso("ES", "63") == "MD"

    def test_italy_lazio(self):
        """Italian FIPS 07 converts to ISO 62 (Lazio)."""
        assert convert_region_to_iso("IT", "07") == "62"

    def test_unknown_country_returns_original(self):
        """Unknown country returns original region code."""
        assert convert_region_to_iso("XX", "99") == "99"

    def test_unknown_region_returns_original(self):
        """Unknown region code for known country returns original."""
        assert convert_region_to_iso("FR", "ZZ") == "ZZ"

    def test_us_regions_pass_through(self):
        """US regions (already ISO) pass through unchanged."""
        # US uses ISO codes in Matomo, so not in our mapping
        assert convert_region_to_iso("US", "CA") == "CA"
        assert convert_region_to_iso("US", "NY") == "NY"

    def test_switzerland_zurich(self):
        """Swiss FIPS 26 converts to ISO ZH (Zürich)."""
        assert convert_region_to_iso("CH", "26") == "ZH"

    def test_netherlands_noord_holland(self):
        """Dutch FIPS 09 converts to ISO NH (Noord-Holland)."""
        assert convert_region_to_iso("NL", "09") == "NH"

    def test_belgium_brussels(self):
        """Belgian FIPS 03 converts to ISO BRU (Brussels)."""
        assert convert_region_to_iso("BE", "03") == "BRU"
