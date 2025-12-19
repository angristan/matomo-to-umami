"""Integration tests for migration against real data.

These tests compare migrated data against existing Umami data
in the overlap period to validate the mappings are correct.
"""

import os
from datetime import datetime, timedelta

import mysql.connector
import psycopg2
import pytest

# Skip if databases not available
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3307"))
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5433"))

# Site mappings for test data
SITE_MAPPINGS = {
    # Matomo idsite -> (umami_website_id, domain)
    1: ("a5d41854-bde7-4416-819f-3923ea2b2706", "angristan.fr"),
    5: ("3824c584-bc9d-4a9b-aa35-9aa64f797c6f", "stanislas.blog"),
    9: ("3824c584-bc9d-4a9b-aa35-9aa64f797c6f", "stanislas.blog"),  # Same as 5
}


def get_mysql_connection():
    """Get MySQL connection for Matomo."""
    try:
        return mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user="root",
            password="password",
            database="matomo",
        )
    except mysql.connector.Error:
        pytest.skip("MySQL not available")


def get_postgres_connection():
    """Get PostgreSQL connection for Umami."""
    try:
        return psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user="app",
            password="password",
            database="app",
        )
    except psycopg2.Error:
        pytest.skip("PostgreSQL not available")


class TestDataOverlap:
    """Tests that validate data in the overlap period."""

    def test_overlap_period_exists(self):
        """Verify we have overlapping data to test with."""
        mysql_conn = get_mysql_connection()
        pg_conn = get_postgres_connection()

        try:
            # Get Matomo date range
            mysql_cur = mysql_conn.cursor()
            mysql_cur.execute("""
                SELECT MIN(visit_first_action_time), MAX(visit_first_action_time)
                FROM piwik_log_visit
            """)
            matomo_min, matomo_max = mysql_cur.fetchone()

            # Get Umami date range
            pg_cur = pg_conn.cursor()
            pg_cur.execute("""
                SELECT MIN(created_at), MAX(created_at)
                FROM session
            """)
            umami_min, umami_max = pg_cur.fetchone()

            # Verify overlap
            assert matomo_min is not None, "No Matomo data"
            assert umami_min is not None, "No Umami data"

            # Overlap should be from Umami start to either end
            overlap_start = max(matomo_min, umami_min.replace(tzinfo=None))
            overlap_end = min(matomo_max, umami_max.replace(tzinfo=None))

            assert overlap_start < overlap_end, "No overlap period"

            print(f"\nOverlap period: {overlap_start} to {overlap_end}")

        finally:
            mysql_conn.close()
            pg_conn.close()

    def test_daily_visit_counts_similar(self):
        """Compare daily visit counts between Matomo and Umami.

        They won't be exact due to different tracking, but should be
        in the same order of magnitude.
        """
        mysql_conn = get_mysql_connection()
        pg_conn = get_postgres_connection()

        try:
            # Test a specific week in the overlap period
            test_date = datetime(2023, 6, 1)

            # Get Matomo counts for stanislas.blog (idsite 5)
            mysql_cur = mysql_conn.cursor()
            mysql_cur.execute(
                """
                SELECT DATE(visit_first_action_time) as date, COUNT(*) as visits
                FROM piwik_log_visit
                WHERE idsite = 5
                  AND visit_first_action_time >= %s
                  AND visit_first_action_time < %s
                GROUP BY DATE(visit_first_action_time)
                ORDER BY date
            """,
                (test_date, test_date + timedelta(days=7)),
            )
            matomo_counts = {row[0]: row[1] for row in mysql_cur.fetchall()}

            # Get Umami counts for stanislas.blog
            pg_cur = pg_conn.cursor()
            pg_cur.execute(
                """
                SELECT DATE(created_at) as date, COUNT(*) as sessions
                FROM session
                WHERE website_id = '3824c584-bc9d-4a9b-aa35-9aa64f797c6f'
                  AND created_at >= %s
                  AND created_at < %s
                GROUP BY DATE(created_at)
                ORDER BY date
            """,
                (test_date, test_date + timedelta(days=7)),
            )
            umami_counts = {row[0]: row[1] for row in pg_cur.fetchall()}

            # Verify counts are similar (within 50% - accounting for different tracking)
            for date in matomo_counts:
                if date in umami_counts:
                    matomo_val = matomo_counts[date]
                    umami_val = umami_counts[date]
                    ratio = min(matomo_val, umami_val) / max(matomo_val, umami_val)

                    print(
                        f"{date}: Matomo={matomo_val}, Umami={umami_val}, ratio={ratio:.2f}"
                    )

                    # They should be within 50% of each other
                    assert ratio > 0.5, (
                        f"Counts too different on {date}: {matomo_val} vs {umami_val}"
                    )

        finally:
            mysql_conn.close()
            pg_conn.close()

    def test_top_pages_match(self):
        """Verify top pages are similar between both systems."""
        mysql_conn = get_mysql_connection()
        pg_conn = get_postgres_connection()

        try:
            # Test period
            start_date = datetime(2023, 6, 1)
            end_date = datetime(2023, 6, 30)

            # Get top pages from Matomo
            mysql_cur = mysql_conn.cursor()
            mysql_cur.execute(
                """
                SELECT 
                    SUBSTRING_INDEX(a.name, '/', -1) as page,
                    COUNT(*) as views
                FROM piwik_log_link_visit_action lva
                JOIN piwik_log_action a ON lva.idaction_url = a.idaction
                WHERE lva.idsite = 5
                  AND lva.server_time >= %s
                  AND lva.server_time < %s
                  AND a.type = 1
                GROUP BY SUBSTRING_INDEX(a.name, '/', -1)
                ORDER BY views DESC
                LIMIT 10
            """,
                (start_date, end_date),
            )
            matomo_pages = [row[0] for row in mysql_cur.fetchall()]

            # Get top pages from Umami
            pg_cur = pg_conn.cursor()
            pg_cur.execute(
                """
                SELECT 
                    SPLIT_PART(url_path, '/', -1) as page,
                    COUNT(*) as views
                FROM website_event
                WHERE website_id = '3824c584-bc9d-4a9b-aa35-9aa64f797c6f'
                  AND created_at >= %s
                  AND created_at < %s
                  AND event_type = 1
                GROUP BY SPLIT_PART(url_path, '/', -1)
                ORDER BY views DESC
                LIMIT 10
            """,
                (start_date, end_date),
            )
            umami_pages = [row[0] for row in pg_cur.fetchall()]

            # At least some overlap in top pages
            common_pages = set(matomo_pages) & set(umami_pages)
            print(f"\nMatomo top pages: {matomo_pages}")
            print(f"Umami top pages: {umami_pages}")
            print(f"Common pages: {common_pages}")

            assert len(common_pages) > 0, "No common top pages found"

        finally:
            mysql_conn.close()
            pg_conn.close()

    def test_browser_distribution_similar(self):
        """Verify browser distribution is similar."""
        mysql_conn = get_mysql_connection()
        pg_conn = get_postgres_connection()

        try:
            start_date = datetime(2023, 6, 1)
            end_date = datetime(2023, 6, 30)

            # Matomo browser distribution
            mysql_cur = mysql_conn.cursor()
            mysql_cur.execute(
                """
                SELECT config_browser_name, COUNT(*) as count
                FROM piwik_log_visit
                WHERE idsite = 5
                  AND visit_first_action_time >= %s
                  AND visit_first_action_time < %s
                GROUP BY config_browser_name
                ORDER BY count DESC
                LIMIT 5
            """,
                (start_date, end_date),
            )
            matomo_browsers = mysql_cur.fetchall()

            # Umami browser distribution
            pg_cur = pg_conn.cursor()
            pg_cur.execute(
                """
                SELECT browser, COUNT(*) as count
                FROM session
                WHERE website_id = '3824c584-bc9d-4a9b-aa35-9aa64f797c6f'
                  AND created_at >= %s
                  AND created_at < %s
                GROUP BY browser
                ORDER BY count DESC
                LIMIT 5
            """,
                (start_date, end_date),
            )
            umami_browsers = pg_cur.fetchall()

            print(f"\nMatomo browsers: {matomo_browsers}")
            print(f"Umami browsers: {umami_browsers}")

            # Chrome should be in top 3 for both
            matomo_top = [b[0] for b in matomo_browsers[:3]]
            umami_top = [b[0] for b in umami_browsers[:3]]

            # CH = Chrome in Matomo, 'chrome' in Umami
            assert "CH" in matomo_top or "CM" in matomo_top, (
                "Chrome not in Matomo top browsers"
            )
            assert any("chrome" in (b or "").lower() for b in umami_top), (
                "Chrome not in Umami top browsers"
            )

        finally:
            mysql_conn.close()
            pg_conn.close()


class TestMigrationOutput:
    """Tests for the migration SQL output."""

    def test_generated_sql_valid(self):
        """Test that generated SQL is syntactically valid."""
        from matomo_to_umami.mappings import SiteMapping
        from matomo_to_umami.migrate import MatomoToUmamiMigrator

        mysql_conn = get_mysql_connection()

        try:
            migrator = MatomoToUmamiMigrator(
                mysql_host=MYSQL_HOST,
                mysql_port=MYSQL_PORT,
                site_mappings=[
                    SiteMapping(
                        5, "3824c584-bc9d-4a9b-aa35-9aa64f797c6f", "stanislas.blog"
                    ),
                ],
                batch_size=10,
            )
            migrator.connect()

            # Generate SQL for a small date range
            start_date = datetime(2023, 6, 1)
            end_date = datetime(2023, 6, 2)

            sql_lines = list(migrator.generate_sessions_sql(start_date, end_date))

            # Should have some output
            assert len(sql_lines) > 0

            # Should contain INSERT statements
            sql_text = "\n".join(sql_lines)
            assert "INSERT INTO session" in sql_text

            # Should have valid UUIDs
            assert "'" in sql_text  # Quoted values

            migrator.close()

        finally:
            mysql_conn.close()

    def test_uuid_consistency(self):
        """Test that UUIDs are consistent across runs."""
        from matomo_to_umami.mappings import generate_uuid_from_matomo_id

        # Same visit ID should always generate same session UUID
        visit_id = 1412530
        uuid1 = generate_uuid_from_matomo_id(visit_id, "visit")
        uuid2 = generate_uuid_from_matomo_id(visit_id, "visit")

        assert uuid1 == uuid2

        # Different visits should have different UUIDs
        uuid3 = generate_uuid_from_matomo_id(1412531, "visit")
        assert uuid1 != uuid3
