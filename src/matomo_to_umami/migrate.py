"""Migration script to convert Matomo data to Umami SQL."""

import argparse
import logging
import re
import sys
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TextIO

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector.connection import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .mappings import (
    SiteMapping,
    generate_uuid_from_matomo_id,
    map_browser,
    map_device_type,
    map_os,
    parse_matomo_url,
    parse_referrer_url,
    truncate_field,
)


@dataclass(frozen=True)
class WhereClause:
    """Represents a parameterized WHERE clause."""

    sql: str
    params: tuple[Any, ...]

    def with_extra_condition(self, condition: str, param: Any) -> WhereClause:
        """Return a new WhereClause with an additional condition."""
        return WhereClause(
            sql=f"{self.sql} AND {condition}",
            params=(*self.params, param),
        )

console = Console(stderr=True)
logger = logging.getLogger(__name__)


def setup_logging(verbosity: int = 0) -> None:
    """Configure logging based on verbosity level.

    Args:
        verbosity: 0=WARNING, 1=INFO, 2+=DEBUG
    """
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


class MigrationError(Exception):
    """Base exception for migration errors."""

    pass


class DatabaseConnectionError(MigrationError):
    """Raised when database connection fails."""

    pass


class SiteMappingError(MigrationError):
    """Raised when site mapping parsing fails."""

    pass


def validate_site_mapping(mapping_str: str) -> SiteMapping:
    """Parse and validate a site mapping string.

    Args:
        mapping_str: Format "matomo_id:umami_uuid:domain"

    Returns:
        SiteMapping object

    Raises:
        SiteMappingError: If the mapping string is invalid
    """
    parts = mapping_str.split(":")

    if len(parts) < 3:
        raise SiteMappingError(
            f"Invalid site mapping format: '{mapping_str}'\n"
            f"Expected format: matomo_id:umami_uuid:domain\n"
            f"Example: 1:550e8400-e29b-41d4-a716-446655440000:example.com"
        )

    # Parse matomo_id
    try:
        matomo_id = int(parts[0])
        if matomo_id <= 0:
            raise SiteMappingError(
                f"Invalid Matomo site ID: '{parts[0]}' (must be a positive integer)"
            )
    except ValueError:
        raise SiteMappingError(
            f"Invalid Matomo site ID: '{parts[0]}' (must be an integer)"
        )

    # Handle UUID which contains colons - rejoin all parts except first and last
    domain = parts[-1]
    umami_uuid = ":".join(parts[1:-1])

    # Validate UUID format
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    if not uuid_pattern.match(umami_uuid):
        raise SiteMappingError(
            f"Invalid Umami UUID: '{umami_uuid}'\n"
            f"Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        )

    # Validate domain
    if not domain or domain.startswith(".") or " " in domain:
        raise SiteMappingError(
            f"Invalid domain: '{domain}'\n"
            f"Domain should be a valid hostname (e.g., example.com)"
        )

    return SiteMapping(
        matomo_idsite=matomo_id,
        umami_website_id=umami_uuid,
        domain=domain,
    )


def escape_sql_string(value: str | None, max_length: int | None = None) -> str:
    """Escape a string for SQL insertion.

    If max_length is provided, truncates BEFORE escaping to ensure
    the final unescaped value fits in the database column.

    Note: PostgreSQL with standard_conforming_strings=on (default) treats
    backslashes as literal characters, so we only escape single quotes.
    """
    if value is None:
        return "NULL"
    # Truncate before escaping if max_length specified
    if max_length is not None and len(value) > max_length:
        value = value[:max_length]
    # Only escape single quotes (backslashes are literal in standard SQL)
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def format_timestamp(dt: datetime | None) -> str:
    """Format datetime for PostgreSQL."""
    if dt is None:
        return "NULL"
    return f"'{dt.isoformat()}'"


class MatomoToUmamiMigrator:
    """Handles migration from Matomo to Umami."""

    conn: MySQLConnection
    cursor: MySQLCursorDict

    def __init__(
        self,
        mysql_host: str = "localhost",
        mysql_port: int = 3306,
        mysql_user: str = "root",
        mysql_password: str = "password",
        mysql_database: str = "matomo",
        site_mappings: list[SiteMapping] | None = None,
        batch_size: int = 1000,
    ) -> None:
        self.mysql_config: dict[str, Any] = {
            "host": mysql_host,
            "port": mysql_port,
            "user": mysql_user,
            "password": mysql_password,
            "database": mysql_database,
        }
        self.site_mappings: list[SiteMapping] = site_mappings or []
        self.batch_size: int = batch_size
        self._site_map: dict[int, SiteMapping] = {
            m.matomo_idsite: m for m in self.site_mappings
        }

    def connect(self) -> None:
        """Connect to Matomo MySQL database.

        Raises:
            DatabaseConnectionError: If connection fails
        """
        logger.info(
            f"Connecting to MySQL at {self.mysql_config['host']}:{self.mysql_config['port']}"
        )
        try:
            self.conn = mysql.connector.connect(**self.mysql_config)
            self.cursor = self.conn.cursor(dictionary=True)
            logger.info("Successfully connected to MySQL database")
        except MySQLError as e:
            error_code = e.errno if hasattr(e, "errno") else "unknown"
            if error_code == 1045:  # Access denied
                raise DatabaseConnectionError(
                    f"Access denied for user '{self.mysql_config['user']}'\n"
                    f"Please check your MySQL username and password."
                ) from e
            elif error_code == 2003:  # Can't connect
                raise DatabaseConnectionError(
                    f"Cannot connect to MySQL server at "
                    f"'{self.mysql_config['host']}:{self.mysql_config['port']}'\n"
                    f"Please check that the server is running and accessible."
                ) from e
            elif error_code == 1049:  # Unknown database
                raise DatabaseConnectionError(
                    f"Database '{self.mysql_config['database']}' does not exist.\n"
                    f"Please check your database name."
                ) from e
            else:
                raise DatabaseConnectionError(f"Failed to connect to MySQL: {e}") from e

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self, "cursor"):
            self.cursor.close()
        if hasattr(self, "conn"):
            self.conn.close()

    def get_site_mapping(self, idsite: int) -> SiteMapping | None:
        """Get Umami website ID for a Matomo site ID."""
        return self._site_map.get(idsite)

    def _build_session_where(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> WhereClause:
        """Build WHERE clause and params for session queries.

        Args:
            start_date: Optional start date filter (inclusive)
            end_date: Optional end date filter (exclusive)

        Returns:
            WhereClause with parameterized SQL and parameter tuple
        """
        where_parts: list[str] = ["1=1"]
        params: list[Any] = []

        if self.site_mappings:
            site_ids = tuple(m.matomo_idsite for m in self.site_mappings)
            placeholders = ", ".join(["%s"] * len(site_ids))
            where_parts.append(f"v.idsite IN ({placeholders})")
            params.extend(site_ids)

        if start_date is not None:
            where_parts.append("v.visit_first_action_time >= %s")
            params.append(start_date)

        if end_date is not None:
            where_parts.append("v.visit_first_action_time < %s")
            params.append(end_date)

        return WhereClause(sql=" AND ".join(where_parts), params=tuple(params))

    def _build_event_where(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> WhereClause:
        """Build WHERE clause and params for event queries.

        Args:
            start_date: Optional start date filter (inclusive)
            end_date: Optional end date filter (exclusive)

        Returns:
            WhereClause with parameterized SQL and parameter tuple
        """
        where_parts: list[str] = ["1=1"]
        params: list[Any] = []

        if self.site_mappings:
            site_ids = tuple(m.matomo_idsite for m in self.site_mappings)
            placeholders = ", ".join(["%s"] * len(site_ids))
            where_parts.append(f"lva.idsite IN ({placeholders})")
            params.extend(site_ids)

        if start_date is not None:
            where_parts.append("lva.server_time >= %s")
            params.append(start_date)

        if end_date is not None:
            where_parts.append("lva.server_time < %s")
            params.append(end_date)

        return WhereClause(sql=" AND ".join(where_parts), params=tuple(params))

    def count_sessions(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """Count total sessions to migrate."""
        where = self._build_session_where(start_date, end_date)
        query = f"SELECT COUNT(*) as cnt FROM piwik_log_visit v WHERE {where.sql}"
        self.cursor.execute(query, where.params)
        result = self.cursor.fetchone()
        count: int = result["cnt"] if result else 0
        logger.debug(f"Found {count:,} sessions to migrate")
        return count

    def count_events(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """Count total events to migrate (pageviews, outlinks, downloads)."""
        where = self._build_event_where(start_date, end_date)
        query = f"""
            SELECT COUNT(*) as cnt
            FROM piwik_log_link_visit_action lva
            JOIN piwik_log_action url_action ON lva.idaction_url = url_action.idaction
            WHERE {where.sql}
              AND lva.idaction_url IS NOT NULL
              AND url_action.type IN (1, 2, 3)
        """
        self.cursor.execute(query, where.params)
        result = self.cursor.fetchone()
        count: int = result["cnt"] if result else 0
        logger.debug(f"Found {count:,} events to migrate")
        return count

    def get_date_range(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, datetime | None]:
        """Get the actual date range of data to be migrated."""
        where = self._build_session_where(start_date, end_date)
        query = f"""
            SELECT
                MIN(v.visit_first_action_time) as min_date,
                MAX(v.visit_first_action_time) as max_date
            FROM piwik_log_visit v
            WHERE {where.sql}
        """
        self.cursor.execute(query, where.params)
        result = self.cursor.fetchone()
        if result:
            return {
                "min_date": result["min_date"],
                "max_date": result["max_date"],
            }
        return {"min_date": None, "max_date": None}

    def get_summary(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get a summary of data to be migrated.

        Returns:
            Dict with session_count, event_count, date_range, and site details
        """
        session_count = self.count_sessions(start_date, end_date)
        event_count = self.count_events(start_date, end_date)
        date_range = self.get_date_range(start_date, end_date)

        # Get per-site breakdown
        site_breakdown: list[dict[str, Any]] = []
        for mapping in self.site_mappings:
            session_where = self._build_session_where(start_date, end_date)
            extra_where = session_where.with_extra_condition(
                "v.idsite = %s", mapping.matomo_idsite
            )
            query = f"""
                SELECT COUNT(*) as cnt FROM piwik_log_visit v
                WHERE {extra_where.sql}
            """
            self.cursor.execute(query, extra_where.params)
            result = self.cursor.fetchone()
            site_sessions: int = result["cnt"] if result else 0

            event_where = self._build_event_where(start_date, end_date)
            extra_where = event_where.with_extra_condition(
                "lva.idsite = %s AND lva.idaction_url IS NOT NULL",
                mapping.matomo_idsite,
            )
            query = f"""
                SELECT COUNT(*) as cnt FROM piwik_log_link_visit_action lva
                JOIN piwik_log_action url_action ON lva.idaction_url = url_action.idaction
                WHERE {extra_where.sql}
                  AND url_action.type IN (1, 2, 3)
            """
            self.cursor.execute(query, extra_where.params)
            result = self.cursor.fetchone()
            site_events: int = result["cnt"] if result else 0

            site_breakdown.append(
                {
                    "matomo_id": mapping.matomo_idsite,
                    "umami_id": mapping.umami_website_id,
                    "domain": mapping.domain,
                    "sessions": site_sessions,
                    "events": site_events,
                }
            )

        return {
            "session_count": session_count,
            "event_count": event_count,
            "date_range": date_range,
            "sites": site_breakdown,
        }

    def print_summary(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Print a formatted summary table and return the summary data."""
        summary = self.get_summary(start_date, end_date)

        # Create summary table
        table = Table(title="Migration Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Sessions", f"{summary['session_count']:,}")
        table.add_row("Total Events", f"{summary['event_count']:,}")

        if summary["date_range"]["min_date"]:
            table.add_row("Date Range Start", str(summary["date_range"]["min_date"]))
            table.add_row("Date Range End", str(summary["date_range"]["max_date"]))
        else:
            table.add_row("Date Range", "No data found")

        console.print(table)

        # Site breakdown table
        if summary["sites"]:
            site_table = Table(title="Per-Site Breakdown")
            site_table.add_column("Matomo ID", style="cyan")
            site_table.add_column("Domain", style="blue")
            site_table.add_column("Sessions", style="green", justify="right")
            site_table.add_column("Events", style="green", justify="right")

            for site in summary["sites"]:
                site_table.add_row(
                    str(site["matomo_id"]),
                    site["domain"],
                    f"{site['sessions']:,}",
                    f"{site['events']:,}",
                )

            console.print(site_table)

        return summary

    def generate_sessions_sql(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> Generator[str]:
        """Generate SQL INSERT statements for sessions."""
        where = self._build_session_where(start_date, end_date)

        query = f"""
            SELECT
                v.idvisit,
                v.idsite,
                v.idvisitor,
                v.visit_first_action_time,
                v.config_browser_name,
                v.config_os,
                v.config_device_type,
                v.config_resolution,
                v.location_browser_lang,
                v.location_country,
                v.location_region,
                v.location_city
            FROM piwik_log_visit v
            WHERE {where.sql}
            ORDER BY v.idvisit
        """

        self.cursor.execute(query, where.params)

        yield "-- Sessions (from piwik_log_visit)"
        yield "-- Maps to Umami session table"
        yield ""

        batch = []
        for row in self.cursor:
            mapping = self.get_site_mapping(row["idsite"])
            if not mapping:
                continue

            session_id = generate_uuid_from_matomo_id(row["idvisit"], "visit")

            # Map fields
            browser = truncate_field(map_browser(row["config_browser_name"]), 20)
            os = truncate_field(map_os(row["config_os"]), 20)
            device = truncate_field(map_device_type(row["config_device_type"]), 20)
            screen = truncate_field(row["config_resolution"], 11)
            language = truncate_field(row["location_browser_lang"], 35)
            country = row["location_country"][:2].upper() if row["location_country"] else None
            # Region should be in {country}-{region} format for Umami
            raw_region = row["location_region"]
            if raw_region and country:
                if "-" not in raw_region:
                    region = f"{country}-{raw_region}"
                else:
                    region = raw_region
            else:
                region = None
            region = truncate_field(region, 20)
            city = truncate_field(row["location_city"], 50)

            values = (
                f"'{session_id}'",
                f"'{mapping.umami_website_id}'",
                escape_sql_string(browser),
                escape_sql_string(os),
                escape_sql_string(device),
                escape_sql_string(screen),
                escape_sql_string(language),
                escape_sql_string(country),
                escape_sql_string(region),
                escape_sql_string(city),
                format_timestamp(row["visit_first_action_time"]),
                "NULL",  # distinct_id
            )
            batch.append(f"({', '.join(values)})")

            if progress and task_id is not None:
                progress.advance(task_id)

            if len(batch) >= self.batch_size:
                yield self._format_session_insert(batch)
                batch = []

        if batch:
            yield self._format_session_insert(batch)

    def _format_session_insert(self, values: list[str]) -> str:
        """Format a batch INSERT for sessions."""
        return f"""INSERT INTO session (session_id, website_id, browser, os, device, screen, language, country, region, city, created_at, distinct_id)
VALUES
{",".join(values)}
ON CONFLICT (session_id) DO NOTHING;
"""

    def generate_events_sql(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> Generator[str]:
        """Generate SQL INSERT statements for website_event."""
        where = self._build_event_where(start_date, end_date)

        # Join with log_action to get URL, page title, and action type
        # Action types: 1=pageview, 2=outlink, 3=download
        query = f"""
            SELECT
                lva.idlink_va,
                lva.idvisit,
                lva.idsite,
                lva.server_time,
                lva.idpageview,
                url_action.name as url_name,
                url_action.url_prefix,
                url_action.type as action_type,
                title_action.name as page_title,
                ref_action.name as ref_url,
                ref_action.url_prefix as ref_url_prefix,
                v.referer_url
            FROM piwik_log_link_visit_action lva
            LEFT JOIN piwik_log_action url_action ON lva.idaction_url = url_action.idaction
            LEFT JOIN piwik_log_action title_action ON lva.idaction_name = title_action.idaction
            LEFT JOIN piwik_log_action ref_action ON lva.idaction_url_ref = ref_action.idaction
            LEFT JOIN piwik_log_visit v ON lva.idvisit = v.idvisit
            WHERE {where.sql}
              AND lva.idaction_url IS NOT NULL
              AND url_action.type IN (1, 2, 3)
            ORDER BY lva.idlink_va
        """

        self.cursor.execute(query, where.params)

        yield "-- Website Events (from piwik_log_link_visit_action)"
        yield "-- Maps to Umami website_event table"
        yield "-- Outlinks and downloads also generate event_data entries"
        yield ""

        batch: list[str] = []
        event_data_batch: list[str] = []
        for row in self.cursor:
            mapping = self.get_site_mapping(row["idsite"])
            if not mapping:
                continue

            event_id = generate_uuid_from_matomo_id(row["idlink_va"], "action")
            session_id = generate_uuid_from_matomo_id(row["idvisit"], "visit")
            # Use pageview ID for visit_id if available, otherwise generate from action
            if row["idpageview"]:
                visit_id = generate_uuid_from_matomo_id(
                    int.from_bytes(row["idpageview"].encode()[:8], "big")
                    if isinstance(row["idpageview"], str)
                    else row["idpageview"],
                    "pageview",
                )
            else:
                visit_id = generate_uuid_from_matomo_id(row["idlink_va"], "pageview")

            # Parse URL
            if row["url_name"]:
                hostname, url_path, url_query = parse_matomo_url(
                    row["url_name"], row["url_prefix"]
                )
            else:
                hostname, url_path, url_query = mapping.domain, "/", None

            # Parse referrer - prefer action referrer, fall back to visit referrer
            if row["ref_url"]:
                ref_domain, ref_path, ref_query = parse_matomo_url(
                    row["ref_url"], row["ref_url_prefix"]
                )
            elif row["referer_url"]:
                ref_domain, ref_path, ref_query = parse_referrer_url(row["referer_url"])
            else:
                ref_domain, ref_path, ref_query = None, None, None

            # Map Matomo action type to Umami event_type and event_name
            # Matomo: 1=pageview, 2=outlink, 3=download
            # Umami: event_type 1=pageview, 2=custom event
            action_type = row["action_type"]
            if action_type == 1:
                event_type = "1"
                event_name = "NULL"
            elif action_type == 2:
                event_type = "2"
                event_name = "'outlink'"
            elif action_type == 3:
                event_type = "2"
                event_name = "'download'"
            else:
                event_type = "1"
                event_name = "NULL"

            values = (
                f"'{event_id}'",
                f"'{mapping.umami_website_id}'",
                f"'{session_id}'",
                format_timestamp(row["server_time"]),
                escape_sql_string(url_path, 500),
                escape_sql_string(url_query, 500),
                escape_sql_string(ref_path, 500),
                escape_sql_string(ref_query, 500),
                escape_sql_string(ref_domain, 500),
                escape_sql_string(row["page_title"], 500),
                event_type,
                event_name,
                f"'{visit_id}'",
                "NULL",  # tag
                escape_sql_string(hostname, 100),
            )
            batch.append(f"({', '.join(values)})")

            # For outlinks and downloads, also store the URL as event_data
            if action_type in (2, 3):
                # Build full URL for event_data using original Matomo URL
                # (hostname, url_path, url_query already parsed from Matomo URL)
                full_url = ""
                if hostname:
                    full_url = f"https://{hostname}"
                full_url += url_path or ""
                if url_query:
                    full_url += f"?{url_query}"

                event_data_id = generate_uuid_from_matomo_id(
                    row["idlink_va"], "event_data"
                )
                event_data_values = (
                    f"'{event_data_id}'",
                    f"'{mapping.umami_website_id}'",
                    f"'{event_id}'",
                    "'url'",  # data_key
                    escape_sql_string(full_url, 500),  # string_value
                    "NULL",  # number_value
                    "NULL",  # date_value
                    "1",  # data_type = string
                    format_timestamp(row["server_time"]),
                )
                event_data_batch.append(f"({', '.join(event_data_values)})")

            if progress and task_id is not None:
                progress.advance(task_id)

            if len(batch) >= self.batch_size:
                yield self._format_event_insert(batch)
                batch = []

            if len(event_data_batch) >= self.batch_size:
                yield self._format_event_data_insert(event_data_batch)
                event_data_batch = []

        if batch:
            yield self._format_event_insert(batch)
        if event_data_batch:
            yield self._format_event_data_insert(event_data_batch)

    def _format_event_insert(self, values: list[str]) -> str:
        """Format a batch INSERT for events."""
        return f"""INSERT INTO website_event (event_id, website_id, session_id, created_at, url_path, url_query, referrer_path, referrer_query, referrer_domain, page_title, event_type, event_name, visit_id, tag, hostname)
VALUES
{",".join(values)}
ON CONFLICT (event_id) DO NOTHING;
"""

    def _format_event_data_insert(self, values: list[str]) -> str:
        """Format a batch INSERT for event_data (outlink/download URLs)."""
        return f"""INSERT INTO event_data (event_data_id, website_id, website_event_id, data_key, string_value, number_value, date_value, data_type, created_at)
VALUES
{",".join(values)}
ON CONFLICT (event_data_id) DO NOTHING;
"""

    def generate_migration_sql(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        output_file: str | None = None,
    ) -> None:
        """Generate complete migration SQL.

        Uses streaming output to minimize memory usage for large migrations.
        SQL is written directly to the output as it's generated.

        Args:
            start_date: Optional start date filter (inclusive)
            end_date: Optional end date filter (exclusive)
            output_file: Path to output file, or None for stdout
        """
        # Count totals for progress bar
        logger.info("Counting records to migrate...")
        session_count = self.count_sessions(start_date, end_date)
        event_count = self.count_events(start_date, end_date)

        logger.info(
            f"Will migrate {session_count:,} sessions and {event_count:,} events"
        )

        if session_count == 0 and event_count == 0:
            logger.warning("No data to migrate for the specified criteria")
            return

        # Open output file if specified (with explicit buffering for large files)
        out: TextIO
        if output_file:
            out = open(output_file, "w", buffering=1024 * 1024)  # 1MB buffer
            logger.info(f"Writing output to: {output_file}")
        else:
            out = sys.stdout

        batches_written = 0

        def write(line: str) -> None:
            out.write(line + "\n")

        def flush_periodically() -> None:
            """Flush output periodically to ensure data is written."""
            nonlocal batches_written
            batches_written += 1
            # Flush every 100 batches for large files
            if output_file and batches_written % 100 == 0:
                out.flush()

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                # Write header
                write("-- Matomo to Umami Migration SQL")
                write(f"-- Generated at: {datetime.now().isoformat()}")
                write(f"-- Sessions: {session_count:,}")
                write(f"-- Events: {event_count:,}")
                if start_date:
                    write(f"-- Start date: {start_date.isoformat()}")
                if end_date:
                    write(f"-- End date: {end_date.isoformat()}")
                write("")
                write("BEGIN;")
                write("")

                # Sessions
                logger.debug("Generating session SQL...")
                session_task = progress.add_task("Sessions", total=session_count)
                for line in self.generate_sessions_sql(
                    start_date, end_date, progress, session_task
                ):
                    write(line)
                    flush_periodically()

                write("")

                # Events
                logger.debug("Generating event SQL...")
                event_task = progress.add_task("Events", total=event_count)
                for line in self.generate_events_sql(
                    start_date, end_date, progress, event_task
                ):
                    write(line)
                    flush_periodically()

                write("")
                write("COMMIT;")

            # Final flush
            if output_file:
                out.flush()
                logger.info(f"Migration SQL written to {output_file}")
        finally:
            if output_file:
                out.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Matomo data to Umami SQL")
    parser.add_argument("--mysql-host", default="localhost", help="MySQL host")
    parser.add_argument("--mysql-port", type=int, default=3306, help="MySQL port")
    parser.add_argument("--mysql-user", default="root", help="MySQL user")
    parser.add_argument("--mysql-password", default="password", help="MySQL password")
    parser.add_argument("--mysql-database", default="matomo", help="MySQL database")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument(
        "--batch-size", type=int, default=1000, help="Batch size for INSERTs"
    )

    # Site mappings (required)
    parser.add_argument(
        "--site-mapping",
        action="append",
        required=True,
        metavar="MATOMO_ID:UMAMI_UUID:DOMAIN",
        help="Site mapping (can specify multiple times)",
    )

    # Dry run mode
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show migration summary without generating SQL",
    )

    # Verbosity
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )

    args = parser.parse_args()

    # Setup logging based on verbosity
    setup_logging(args.verbose)

    # Parse and validate site mappings
    site_mappings = []
    for mapping_str in args.site_mapping:
        try:
            site_mappings.append(validate_site_mapping(mapping_str))
        except SiteMappingError as e:
            console.print(f"[red]Error:[/red] {e}", highlight=False)
            sys.exit(1)

    logger.info(f"Configured {len(site_mappings)} site mapping(s)")
    for mapping in site_mappings:
        logger.debug(
            f"  Site {mapping.matomo_idsite} -> {mapping.umami_website_id} ({mapping.domain})"
        )

    # Parse dates
    start_date = None
    end_date = None
    try:
        if args.start_date:
            start_date = datetime.fromisoformat(args.start_date)
        if args.end_date:
            end_date = datetime.fromisoformat(args.end_date)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid date format: {e}", highlight=False)
        console.print("Use YYYY-MM-DD format (e.g., 2024-01-15)")
        sys.exit(1)

    migrator = MatomoToUmamiMigrator(
        mysql_host=args.mysql_host,
        mysql_port=args.mysql_port,
        mysql_user=args.mysql_user,
        mysql_password=args.mysql_password,
        mysql_database=args.mysql_database,
        site_mappings=site_mappings,
        batch_size=args.batch_size,
    )

    try:
        migrator.connect()

        if args.dry_run:
            # Dry run mode - just show summary
            console.print(
                "\n[bold cyan]Dry Run Mode[/bold cyan] - No SQL will be generated\n"
            )
            summary = migrator.print_summary(start_date, end_date)

            if summary["session_count"] == 0 and summary["event_count"] == 0:
                console.print(
                    "\n[yellow]Warning:[/yellow] No data found for the specified criteria."
                )
            else:
                console.print(
                    "\n[green]Ready to migrate.[/green] Run without --dry-run to generate SQL."
                )
        else:
            # Full migration
            migrator.generate_migration_sql(
                start_date=start_date,
                end_date=end_date,
                output_file=args.output,
            )
    except DatabaseConnectionError as e:
        console.print(f"[red]Database Error:[/red] {e}", highlight=False)
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Migration cancelled by user[/yellow]")
        sys.exit(130)
    finally:
        migrator.close()


if __name__ == "__main__":
    main()
