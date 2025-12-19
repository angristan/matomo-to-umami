"""Migration script to convert Matomo data to Umami SQL."""

import argparse
import sys
from datetime import datetime
from typing import Generator, Optional
import mysql.connector
from .mappings import (
    SiteMapping,
    generate_uuid_from_matomo_id,
    parse_matomo_url,
    parse_referrer_url,
    map_browser,
    map_os,
    map_device_type,
    truncate_field,
)


def escape_sql_string(value: Optional[str], max_length: Optional[int] = None) -> str:
    """Escape a string for SQL insertion.

    If max_length is provided, truncates BEFORE escaping to ensure
    the final unescaped value fits in the database column.
    """
    if value is None:
        return "NULL"
    # Truncate before escaping if max_length specified
    if max_length is not None and len(value) > max_length:
        value = value[:max_length]
    # Escape single quotes and backslashes
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def format_timestamp(dt: Optional[datetime]) -> str:
    """Format datetime for PostgreSQL."""
    if dt is None:
        return "NULL"
    return f"'{dt.isoformat()}'"


class MatomoToUmamiMigrator:
    """Handles migration from Matomo to Umami."""
    
    def __init__(
        self,
        mysql_host: str = "localhost",
        mysql_port: int = 3306,
        mysql_user: str = "root",
        mysql_password: str = "password",
        mysql_database: str = "matomo",
        site_mappings: list[SiteMapping] = None,
        batch_size: int = 1000,
    ):
        self.mysql_config = {
            "host": mysql_host,
            "port": mysql_port,
            "user": mysql_user,
            "password": mysql_password,
            "database": mysql_database,
        }
        self.site_mappings = site_mappings or []
        self.batch_size = batch_size
        self._site_map = {m.matomo_idsite: m for m in self.site_mappings}
    
    def connect(self):
        """Connect to Matomo MySQL database."""
        self.conn = mysql.connector.connect(**self.mysql_config)
        self.cursor = self.conn.cursor(dictionary=True)
    
    def close(self):
        """Close database connection."""
        if hasattr(self, 'cursor'):
            self.cursor.close()
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_site_mapping(self, idsite: int) -> Optional[SiteMapping]:
        """Get Umami website ID for a Matomo site ID."""
        return self._site_map.get(idsite)
    
    def generate_sessions_sql(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Generator[str, None, None]:
        """Generate SQL INSERT statements for sessions."""
        
        where_clauses = ["1=1"]
        params = []
        
        # Filter by sites we have mappings for
        if self.site_mappings:
            site_ids = [m.matomo_idsite for m in self.site_mappings]
            placeholders = ", ".join(["%s"] * len(site_ids))
            where_clauses.append(f"v.idsite IN ({placeholders})")
            params.extend(site_ids)
        
        if start_date:
            where_clauses.append("v.visit_first_action_time >= %s")
            params.append(start_date)
        
        if end_date:
            where_clauses.append("v.visit_first_action_time < %s")
            params.append(end_date)
        
        where_sql = " AND ".join(where_clauses)
        
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
            WHERE {where_sql}
            ORDER BY v.idvisit
        """
        
        self.cursor.execute(query, params)
        
        yield "-- Sessions (from piwik_log_visit)"
        yield "-- Maps to Umami session table"
        yield ""
        
        batch = []
        for row in self.cursor:
            mapping = self.get_site_mapping(row['idsite'])
            if not mapping:
                continue
            
            session_id = generate_uuid_from_matomo_id(row['idvisit'], 'visit')
            
            # Map fields
            browser = truncate_field(map_browser(row['config_browser_name']), 20)
            os = truncate_field(map_os(row['config_os']), 20)
            device = truncate_field(map_device_type(row['config_device_type']), 20)
            screen = truncate_field(row['config_resolution'], 11)
            language = truncate_field(row['location_browser_lang'], 35)
            country = row['location_country'][:2] if row['location_country'] else None
            region = truncate_field(row['location_region'], 20)
            city = truncate_field(row['location_city'], 50)
            
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
                format_timestamp(row['visit_first_action_time']),
                "NULL",  # distinct_id
            )
            batch.append(f"({', '.join(values)})")
            
            if len(batch) >= self.batch_size:
                yield self._format_session_insert(batch)
                batch = []
        
        if batch:
            yield self._format_session_insert(batch)
    
    def _format_session_insert(self, values: list[str]) -> str:
        """Format a batch INSERT for sessions."""
        return f"""INSERT INTO session (session_id, website_id, browser, os, device, screen, language, country, region, city, created_at, distinct_id)
VALUES
{','.join(values)}
ON CONFLICT (session_id) DO NOTHING;
"""
    
    def generate_events_sql(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Generator[str, None, None]:
        """Generate SQL INSERT statements for website_event."""
        
        where_clauses = ["1=1"]
        params = []
        
        # Filter by sites we have mappings for
        if self.site_mappings:
            site_ids = [m.matomo_idsite for m in self.site_mappings]
            placeholders = ", ".join(["%s"] * len(site_ids))
            where_clauses.append(f"lva.idsite IN ({placeholders})")
            params.extend(site_ids)
        
        if start_date:
            where_clauses.append("lva.server_time >= %s")
            params.append(start_date)
        
        if end_date:
            where_clauses.append("lva.server_time < %s")
            params.append(end_date)
        
        where_sql = " AND ".join(where_clauses)
        
        # Join with log_action to get URL and page title
        query = f"""
            SELECT 
                lva.idlink_va,
                lva.idvisit,
                lva.idsite,
                lva.server_time,
                lva.idpageview,
                url_action.name as url_name,
                url_action.url_prefix,
                title_action.name as page_title,
                ref_action.name as ref_url,
                ref_action.url_prefix as ref_url_prefix,
                v.referer_url
            FROM piwik_log_link_visit_action lva
            LEFT JOIN piwik_log_action url_action ON lva.idaction_url = url_action.idaction
            LEFT JOIN piwik_log_action title_action ON lva.idaction_name = title_action.idaction
            LEFT JOIN piwik_log_action ref_action ON lva.idaction_url_ref = ref_action.idaction
            LEFT JOIN piwik_log_visit v ON lva.idvisit = v.idvisit
            WHERE {where_sql}
              AND lva.idaction_url IS NOT NULL
            ORDER BY lva.idlink_va
        """
        
        self.cursor.execute(query, params)
        
        yield "-- Website Events (from piwik_log_link_visit_action)"
        yield "-- Maps to Umami website_event table"
        yield ""
        
        batch = []
        for row in self.cursor:
            mapping = self.get_site_mapping(row['idsite'])
            if not mapping:
                continue
            
            event_id = generate_uuid_from_matomo_id(row['idlink_va'], 'action')
            session_id = generate_uuid_from_matomo_id(row['idvisit'], 'visit')
            # Use pageview ID for visit_id if available, otherwise generate from action
            if row['idpageview']:
                visit_id = generate_uuid_from_matomo_id(
                    int.from_bytes(row['idpageview'].encode()[:8], 'big') if isinstance(row['idpageview'], str) else row['idpageview'],
                    'pageview'
                )
            else:
                visit_id = generate_uuid_from_matomo_id(row['idlink_va'], 'pageview')
            
            # Parse URL
            if row['url_name']:
                hostname, url_path = parse_matomo_url(row['url_name'], row['url_prefix'])
            else:
                hostname, url_path = mapping.domain, "/"
            
            # Parse referrer - prefer action referrer, fall back to visit referrer
            if row['ref_url']:
                ref_domain, ref_path = parse_matomo_url(row['ref_url'], row['ref_url_prefix'])
            elif row['referer_url']:
                ref_domain, ref_path = parse_referrer_url(row['referer_url'])
            else:
                ref_domain, ref_path = None, None
            
            values = (
                f"'{event_id}'",
                f"'{mapping.umami_website_id}'",
                f"'{session_id}'",
                format_timestamp(row['server_time']),
                escape_sql_string(url_path, 500),
                "NULL",  # url_query - would need to parse from URL
                escape_sql_string(ref_path, 500),
                "NULL",  # referrer_query
                escape_sql_string(ref_domain, 500),
                escape_sql_string(row['page_title'], 500),
                "1",  # event_type = pageview
                "NULL",  # event_name
                f"'{visit_id}'",
                "NULL",  # tag
                escape_sql_string(hostname, 100),
            )
            batch.append(f"({', '.join(values)})")
            
            if len(batch) >= self.batch_size:
                yield self._format_event_insert(batch)
                batch = []
        
        if batch:
            yield self._format_event_insert(batch)
    
    def _format_event_insert(self, values: list[str]) -> str:
        """Format a batch INSERT for events."""
        return f"""INSERT INTO website_event (event_id, website_id, session_id, created_at, url_path, url_query, referrer_path, referrer_query, referrer_domain, page_title, event_type, event_name, visit_id, tag, hostname)
VALUES
{','.join(values)}
ON CONFLICT (event_id) DO NOTHING;
"""
    
    def generate_migration_sql(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        output_file: str = None,
    ):
        """Generate complete migration SQL."""
        
        def write_output(lines):
            if output_file:
                with open(output_file, 'w') as f:
                    for line in lines:
                        f.write(line + "\n")
            else:
                for line in lines:
                    print(line)
        
        def generate_all():
            yield "-- Matomo to Umami Migration SQL"
            yield f"-- Generated at: {datetime.now().isoformat()}"
            if start_date:
                yield f"-- Start date: {start_date.isoformat()}"
            if end_date:
                yield f"-- End date: {end_date.isoformat()}"
            yield ""
            yield "BEGIN;"
            yield ""

            # Sessions first (foreign key dependency)
            for line in self.generate_sessions_sql(start_date, end_date):
                yield line

            yield ""

            # Then events
            for line in self.generate_events_sql(start_date, end_date):
                yield line

            yield ""
            yield "COMMIT;"
        
        write_output(generate_all())


def main():
    parser = argparse.ArgumentParser(description="Migrate Matomo data to Umami SQL")
    parser.add_argument("--mysql-host", default="localhost", help="MySQL host")
    parser.add_argument("--mysql-port", type=int, default=3306, help="MySQL port")
    parser.add_argument("--mysql-user", default="root", help="MySQL user")
    parser.add_argument("--mysql-password", default="password", help="MySQL password")
    parser.add_argument("--mysql-database", default="matomo", help="MySQL database")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for INSERTs")
    
    # Site mappings (required)
    parser.add_argument(
        "--site-mapping",
        action="append",
        required=True,
        help="Site mapping in format: matomo_id:umami_uuid:domain (can specify multiple)"
    )
    
    args = parser.parse_args()
    
    # Parse site mappings
    site_mappings = []
    for mapping_str in args.site_mapping:
        parts = mapping_str.split(":")
        if len(parts) < 3:
            print(f"Error: Invalid site mapping format: {mapping_str}", file=sys.stderr)
            print("Expected format: matomo_id:umami_uuid:domain", file=sys.stderr)
            sys.exit(1)
        
        # Handle UUID which contains colons - rejoin all parts except first and last
        matomo_id = int(parts[0])
        domain = parts[-1]
        umami_uuid = ":".join(parts[1:-1])
        
        site_mappings.append(SiteMapping(
            matomo_idsite=matomo_id,
            umami_website_id=umami_uuid,
            domain=domain,
        ))
    
    # Parse dates
    start_date = None
    end_date = None
    if args.start_date:
        start_date = datetime.fromisoformat(args.start_date)
    if args.end_date:
        end_date = datetime.fromisoformat(args.end_date)
    
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
        migrator.generate_migration_sql(
            start_date=start_date,
            end_date=end_date,
            output_file=args.output,
        )
    finally:
        migrator.close()


if __name__ == "__main__":
    main()
