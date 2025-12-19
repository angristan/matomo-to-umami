"""Tests for field mappings."""

import pytest
from matomo_to_umami.mappings import (
    parse_matomo_url,
    parse_referrer_url,
    map_browser,
    map_os,
    map_device_type,
    generate_uuid_from_matomo_id,
    truncate_field,
)
from matomo_to_umami.migrate import (
    validate_site_mapping,
    SiteMappingError,
)


class TestParseMatmoUrl:
    """Tests for parse_matomo_url function."""
    
    def test_prefix_0_with_path(self):
        """URL prefix 0 includes domain in name."""
        hostname, path = parse_matomo_url("stanislas.blog/2019/01/wireguard/", 0)
        assert hostname == "stanislas.blog"
        assert path == "/2019/01/wireguard/"
    
    def test_prefix_0_root(self):
        """URL prefix 0 with just domain."""
        hostname, path = parse_matomo_url("angristan.fr", 0)
        assert hostname == "angristan.fr"
        assert path == "/"
    
    def test_prefix_2_https(self):
        """URL prefix 2 = https://"""
        hostname, path = parse_matomo_url("stanislas.blog/path/to/page", 2)
        assert hostname == "stanislas.blog"
        assert path == "/path/to/page"
    
    def test_prefix_3_https_www(self):
        """URL prefix 3 = https://www."""
        hostname, path = parse_matomo_url("example.com/page", 3)
        assert hostname == "www.example.com"
        assert path == "/page"
    
    def test_prefix_none_defaults_to_0(self):
        """None prefix treated as 0."""
        hostname, path = parse_matomo_url("example.com/test", None)
        assert hostname == "example.com"
        assert path == "/test"


class TestParseReferrerUrl:
    """Tests for parse_referrer_url function."""
    
    def test_full_url_with_path(self):
        hostname, path = parse_referrer_url("https://www.google.com/search?q=test")
        assert hostname == "www.google.com"
        assert path == "/search?q=test"
    
    def test_url_without_protocol(self):
        hostname, path = parse_referrer_url("google.com/")
        assert hostname == "google.com"
        assert path == "/"
    
    def test_none_input(self):
        hostname, path = parse_referrer_url(None)
        assert hostname is None
        assert path is None
    
    def test_empty_string(self):
        hostname, path = parse_referrer_url("")
        assert hostname is None
        assert path is None


class TestMapBrowser:
    """Tests for browser code mapping."""
    
    def test_chrome(self):
        assert map_browser("CH") == "chrome"
    
    def test_firefox(self):
        assert map_browser("FF") == "firefox"
    
    def test_safari(self):
        assert map_browser("SF") == "safari"
    
    def test_chrome_mobile(self):
        assert map_browser("CM") == "chrome-mobile"
    
    def test_unknown_browser_lowercased(self):
        assert map_browser("XX") == "xx"
    
    def test_none(self):
        assert map_browser(None) is None


class TestMapOs:
    """Tests for OS code mapping."""
    
    def test_windows(self):
        assert map_os("WIN") == "windows"
    
    def test_macos(self):
        assert map_os("MAC") == "mac-os"
    
    def test_linux(self):
        assert map_os("LIN") == "linux"
    
    def test_android(self):
        assert map_os("AND") == "android"
    
    def test_ios(self):
        assert map_os("IOS") == "ios"
    
    def test_unknown_os_lowercased(self):
        assert map_os("XXX") == "xxx"
    
    def test_none(self):
        assert map_os(None) is None


class TestMapDeviceType:
    """Tests for device type mapping."""
    
    def test_desktop(self):
        assert map_device_type(0) == "desktop"
    
    def test_smartphone(self):
        assert map_device_type(1) == "smartphone"
    
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
        mapping = validate_site_mapping("1:550e8400-e29b-41d4-a716-446655440000:example.com")
        assert mapping.matomo_idsite == 1
        assert mapping.umami_website_id == "550e8400-e29b-41d4-a716-446655440000"
        assert mapping.domain == "example.com"

    def test_valid_mapping_with_subdomain(self):
        """Domain can include subdomains."""
        mapping = validate_site_mapping("2:550e8400-e29b-41d4-a716-446655440000:www.example.com")
        assert mapping.domain == "www.example.com"

    def test_invalid_format_too_few_parts(self):
        """Mapping with too few parts raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("1:example.com")
        assert "Invalid site mapping format" in str(excinfo.value)

    def test_invalid_matomo_id_not_integer(self):
        """Non-integer Matomo ID raises error."""
        with pytest.raises(SiteMappingError) as excinfo:
            validate_site_mapping("abc:550e8400-e29b-41d4-a716-446655440000:example.com")
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
    """Tests for expanded browser mappings."""

    def test_brave(self):
        assert map_browser("BR") == "brave"

    def test_vivaldi(self):
        assert map_browser("VI") == "vivaldi"

    def test_arc(self):
        assert map_browser("AR") == "arc"

    def test_duckduckgo(self):
        assert map_browser("DU") == "duckduckgo"

    def test_tor(self):
        assert map_browser("TH") == "tor"


class TestExpandedOSMappings:
    """Tests for expanded OS mappings."""

    def test_harmonyos(self):
        assert map_os("HAR") == "harmonyos"

    def test_arch(self):
        assert map_os("ARC") == "arch"

    def test_pop_os(self):
        assert map_os("POP") == "pop-os"

    def test_freebsd(self):
        assert map_os("FRE") == "freebsd"
