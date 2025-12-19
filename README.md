# Matomo to Umami Migration Tool

A Python tool to migrate analytics data from Matomo (MySQL/MariaDB) to Umami (PostgreSQL). It extracts visitor sessions and pageview events from a Matomo database and generates SQL INSERT statements compatible with Umami's schema.

## What This Tool Does

This migration tool:

1. **Extracts sessions** from Matomo's `piwik_log_visit` table and converts them to Umami's `session` table format
2. **Extracts pageview events** from Matomo's `piwik_log_link_visit_action` table (joined with `piwik_log_action`) and converts them to Umami's `website_event` table format
3. **Generates deterministic UUIDs** using UUID v5 so re-running the migration produces identical IDs
4. **Outputs SQL files** with `ON CONFLICT DO NOTHING` for safe, idempotent imports

## What's Covered

| Feature              | Status                          |
| -------------------- | ------------------------------- |
| Session/visitor data | Covered                         |
| Pageview events      | Covered                         |
| Browser detection    | Covered (with code mapping)     |
| OS detection         | Covered (with code mapping)     |
| Device type          | Covered (desktop/mobile/tablet) |
| Screen resolution    | Covered                         |
| Language             | Covered                         |
| Country/Region/City  | Covered                         |
| Page URLs            | Covered                         |
| Page titles          | Covered                         |
| Referrer URLs        | Covered (with fallback logic)   |
| Multi-site support   | Covered                         |
| Date range filtering | Covered                         |
| Batch processing     | Covered                         |
| Progress bar         | Covered                         |

## What's NOT Covered

| Feature                | Reason                                     |
| ---------------------- | ------------------------------------------ |
| Custom events          | Only pageviews (event_type=1) are migrated |
| E-commerce/Goals       | Umami has different tracking model         |
| Site search data       | Not mapped                                 |
| Conversion tracking    | Different architecture                     |
| URL query parameters   | Stored separately in Umami, not extracted  |
| Real-time data         | Only historical batch migration            |
| User accounts/segments | Not applicable                             |

## How It Works

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Matomo (MySQL)                          │
│  ┌──────────────────┐    ┌─────────────────────────────┐   │
│  │ piwik_log_visit  │    │ piwik_log_link_visit_action │   │
│  │ (sessions)       │    │ (pageviews)                 │   │
│  └────────┬─────────┘    └──────────────┬──────────────┘   │
│           │                              │                  │
└───────────┼──────────────────────────────┼──────────────────┘
            │                              │
            ▼                              ▼
    ┌───────────────────────────────────────────────┐
    │           Migration Script                     │
    │  • Field mapping (browser/OS/device codes)    │
    │  • UUID v5 generation (deterministic)         │
    │  • URL parsing (Matomo prefix system)         │
    │  • SQL escaping and batching                  │
    └───────────────────────────────────────────────┘
            │                              │
            ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Umami (PostgreSQL)                      │
│  ┌──────────────────┐    ┌─────────────────────────────┐   │
│  │ session          │    │ website_event               │   │
│  └──────────────────┘    └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### UUID Generation

The tool generates deterministic UUIDs using UUID v5 with the RFC 4122 URL namespace. Each entity type has a prefix:

```python
matomo:visit:{idvisit}     → session.session_id
matomo:action:{idlink_va}  → website_event.event_id
```

This means running the migration twice produces identical UUIDs, making the process idempotent.

## Getting Started

### Prerequisites

- Python 3.12+
- Access to your Matomo MySQL/MariaDB database
- A running Umami instance with PostgreSQL

### Installation

```bash
git clone https://github.com/your-username/matomo-to-umami.git
cd matomo-to-umami
uv sync
```

### Usage

> **Important**: Before migrating, run both Matomo and Umami tracking on your websites in parallel for a while. This prevents data gaps during the transition period.

While the script can connect directly to remote databases, we recommend dumping locally and testing the migration against a local Umami instance first. This lets you verify the data looks correct before importing into production.

#### 1. Start the local environment

```bash
docker-compose up -d

# Services:
#   MariaDB (Matomo):  localhost:3307, root/password
#   PostgreSQL:        localhost:5433, app/password
#   Umami Dashboard:   http://localhost:3000
```

#### 2. Load your database dumps

```bash
# Export from production
mysqldump -h your-matomo-host -u user -p matomo > dumps/matomo.sql
pg_dump -h your-umami-host -U user umami > dumps/umami.sql

# Load into local containers
docker exec -i matomo-mariadb mysql -u root -ppassword matomo < dumps/matomo.sql
docker exec -i umami-postgres psql -U app -d app < dumps/umami.sql
```

#### 3. Identify your site mappings

Map each Matomo site ID to its corresponding Umami website UUID:

```bash
# Get Matomo site IDs
docker exec -i matomo-mariadb mysql -u root -ppassword matomo \
  -e "SELECT idsite, name, main_url FROM piwik_site"

# +--------+------------------+-------------------------+
# | idsite | name             | main_url                |
# +--------+------------------+-------------------------+
# |      1 | Example Site     | https://example.com     |
# |      5 | Blog             | https://blog.example.com|
# +--------+------------------+-------------------------+

# Get Umami website UUIDs
docker exec -i umami-postgres psql -U app -d app \
  -c "SELECT website_id, name, domain FROM website"

#               website_id              |      name      |      domain
# --------------------------------------+----------------+------------------
#  a5d41854-bde7-4416-819f-3923ea2b2706 | Example Site   | example.com
#  3824c584-bc9d-4a9b-aa35-9aa64f797c6f | Blog           | blog.example.com
```

#### 4. Generate the migration SQL

```bash
migrate \
  --mysql-host localhost \
  --mysql-port 3307 \
  --mysql-user root \
  --mysql-password password \
  --mysql-database matomo \
  --site-mapping "1:a5d41854-bde7-4416-819f-3923ea2b2706:example.com" \
  --site-mapping "5:3824c584-bc9d-4a9b-aa35-9aa64f797c6f:blog.example.com" \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --output migration.sql

# Sessions ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 642648/642648 0:00:07
# Events   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 856788/856788 0:00:15
```

**Parameters:**

| Parameter          | Description                                        |
| ------------------ | -------------------------------------------------- |
| `--mysql-host`     | Matomo database host                               |
| `--mysql-port`     | Matomo database port (default: 3306)               |
| `--mysql-user`     | Database username                                  |
| `--mysql-password` | Database password                                  |
| `--mysql-database` | Matomo database name                               |
| `--site-mapping`   | Format: `matomo_id:umami_uuid:domain` (repeatable) |
| `--start-date`     | Start of date range (YYYY-MM-DD)                   |
| `--end-date`       | End of date range (YYYY-MM-DD)                     |
| `--output`         | Output SQL file (default: stdout)                  |
| `--batch-size`     | Rows per INSERT statement (default: 1000)          |

#### 5. Import into local Umami and verify

```bash
docker exec -i umami-postgres psql -U app -d app < migration.sql
```

Open http://localhost:3000, log in, and verify:

- Pageviews and visits show up in the overview
- Pages list shows your URLs correctly
- Referrers, browsers, OS, devices, and countries look reasonable

#### 6. Import into production

Once satisfied with the local results:

```bash
psql -h your-production-host -U user -d umami < migration.sql
```

The `ON CONFLICT DO NOTHING` clauses make this safe to run multiple times.

#### Resetting the local environment

```bash
docker-compose down -v && docker-compose up -d
```

## How the Migration Works (Technical Details)

### Session Migration

1. Query `piwik_log_visit` filtered by site IDs and date range
2. For each visit:
   - Generate UUID v5 from `idvisit`
   - Map browser/OS/device codes to Umami format
   - Extract first 2 chars of country code
   - Truncate fields to Umami column limits
3. Generate batched INSERT statements with `ON CONFLICT DO NOTHING`

### Event Migration

1. Query `piwik_log_link_visit_action` joined with `piwik_log_action`
2. For each action:
   - Generate UUID v5 from `idlink_va`
   - Parse URL using Matomo's prefix system (0=none, 1=http://, 2=https://, 3=https://www.)
   - Extract referrer from action or fall back to visit-level referrer
   - Set event_type=1 (pageview)
3. Generate batched INSERT statements

### SQL Output Format

```sql
BEGIN;

-- Matomo to Umami Migration
-- Generated: 2024-01-15T10:30:00
-- Site mappings:
--   1 -> a5d41854-bde7-4416-819f-3923ea2b2706 (example.com)

-- Sessions
INSERT INTO session (session_id, website_id, browser, os, device, screen, language, country, region, city, created_at)
VALUES
  ('uuid-1', 'website-uuid', 'chrome', 'windows', 'desktop', '1920x1080', 'en', 'US', NULL, NULL, '2023-01-01 12:00:00'),
  ('uuid-2', ...)
ON CONFLICT (session_id) DO NOTHING;

-- Website Events
INSERT INTO website_event (event_id, website_id, session_id, created_at, url_path, page_title, referrer_domain, referrer_path, event_type, hostname)
VALUES
  ('event-uuid-1', 'website-uuid', 'session-uuid', '2023-01-01 12:00:00', '/blog/post', 'My Post', 'google.com', '/search', 1, 'example.com'),
  ...
ON CONFLICT (event_id) DO NOTHING;

COMMIT;
```

## Limitations and Caveats

1. **Pageviews only**: Custom events, goals, and e-commerce data are not migrated
2. **Historical data**: This is a one-time batch migration, not continuous sync
3. **Tracking differences**: Matomo and Umami count sessions differently, so numbers won't match exactly
4. **No rollback**: The tool generates SQL; there's no built-in rollback mechanism
5. **Large datasets**: For very large Matomo instances, you may need to migrate in date range chunks

## Troubleshooting

**Connection errors**: The tool provides user-friendly error messages for common database issues:

- Access denied: Check your MySQL username and password
- Cannot connect: Verify the server is running and accessible
- Unknown database: Check your database name

**Invalid site mapping**: The tool validates site mappings and provides helpful error messages:

```text
Error: Invalid Umami UUID: 'not-a-uuid'
Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**"Unknown browser code"**: The migration maps unknown codes to the original value. Check if it's a newer browser not in the mapping.

**Duplicate key errors**: The SQL uses `ON CONFLICT DO NOTHING`, so duplicates are safely ignored. This is expected on re-runs.

**Memory issues**: Reduce `--batch-size` for large migrations, or split by date ranges.

**Missing referrers**: If action-level referrer is NULL, the tool falls back to visit-level referrer. Some pageviews may still have no referrer data.

## License

MIT License - see LICENSE file for details.
