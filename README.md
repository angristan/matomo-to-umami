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
# Clone the repository
git clone https://github.com/your-username/matomo-to-umami.git
cd matomo-to-umami

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Usage

#### 1. Identify your site mappings

You need to map each Matomo site ID to its corresponding Umami website UUID:

```bash
# Get Matomo site IDs
mysql -h your-matomo-host -u user -p matomo \
  -e "SELECT idsite, name, main_url FROM piwik_site"

# +--------+------------------+-------------------------+
# | idsite | name             | main_url                |
# +--------+------------------+-------------------------+
# |      1 | Example Site     | https://example.com     |
# |      5 | Blog             | https://blog.example.com|
# +--------+------------------+-------------------------+

# Get Umami website UUIDs (from Umami dashboard or database)
psql -h your-umami-host -U user umami \
  -c "SELECT website_id, name, domain FROM website"

#               website_id              |      name      |      domain
# --------------------------------------+----------------+------------------
#  a5d41854-bde7-4416-819f-3923ea2b2706 | Example Site   | example.com
#  3824c584-bc9d-4a9b-aa35-9aa64f797c6f | Blog           | blog.example.com
```

#### 2. Generate the migration SQL

```bash
migrate \
  --mysql-host localhost \
  --mysql-port 3306 \
  --mysql-user root \
  --mysql-password your-password \
  --mysql-database matomo \
  --site-mapping "1:a5d41854-bde7-4416-819f-3923ea2b2706:example.com" \
  --site-mapping "5:3824c584-bc9d-4a9b-aa35-9aa64f797c6f:blog.example.com" \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --output migration.sql \
  --batch-size 1000
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

#### 3. Import into Umami

```bash
# Review the generated SQL first!
head -100 migration.sql

# Import into Umami PostgreSQL
psql -h your-umami-host -U user umami < migration.sql
```

### Testing the Migration Locally (Recommended)

Before importing into production, **test the migration against a local Umami instance** using the provided Docker Compose setup. This lets you verify the data looks correct in the Umami dashboard.

The workflow is:

1. Export your production Umami database (schema + website definitions)
2. Import it into the local Docker environment
3. Generate and import the migration SQL
4. Verify everything in the local Umami dashboard
5. Once satisfied, import the migration SQL into production

#### Step 1: Start the local environment

```bash
# Start MariaDB (for Matomo data) and PostgreSQL + Umami
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Services:
#   MariaDB (Matomo):  localhost:3307, root/password
#   PostgreSQL:        localhost:5433, app/password
#   Umami Dashboard:   http://localhost:3000
```

#### Step 2: Load your database dumps

```bash
# Load your Matomo dump into MariaDB
docker exec -i matomo-mariadb mysql -u root -ppassword matomo < dumps/matomo.sql

# Load your Umami production dump into PostgreSQL
# This gives you the schema + existing website definitions (with their UUIDs)
docker exec -i umami-postgres psql -U app -d app < dumps/umami.sql
```

> **Tip**: Export your production Umami database with:
>
> ```bash
> pg_dump -h your-prod-host -U user umami > dumps/umami.sql
> ```

#### Step 3: Get your site mappings from the imported data

Since you imported your production Umami dump, the website UUIDs are already there:

```bash
# List websites and their UUIDs from the imported Umami data
docker exec -i umami-postgres psql -U app -d app \
  -c "SELECT website_id, name, domain FROM website"

# List Matomo site IDs
docker exec -i matomo-mariadb mysql -u root -ppassword matomo \
  -e "SELECT idsite, name, main_url FROM piwik_site"
```

Match the Matomo site IDs to the Umami website UUIDs for your `--site-mapping` arguments.

#### Step 4: Generate the migration SQL

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
  --end-date 2023-12-31 \
  --output migration.sql
```

#### Step 5: Import the migration into local Umami

```bash
# Import the migration SQL (adds sessions + events to existing data)
docker exec -i umami-postgres psql -U app -d app < migration.sql

# Check row counts
docker exec -i umami-postgres psql -U app -d app << 'EOF'
SELECT 'sessions' as table_name, COUNT(*) FROM session
UNION ALL
SELECT 'events', COUNT(*) FROM website_event;
EOF
```

#### Step 6: Verify in the Umami dashboard

1. Open http://localhost:3000
2. Log in with your credentials (same as production since you imported the dump)
3. Select your website
4. Adjust the date range to cover your migrated data
5. Verify:
   - **Pageviews and visits** show up in the overview
   - **Pages** list shows your URLs correctly
   - **Referrers** are populated
   - **Browsers/OS/Devices** breakdown looks reasonable
   - **Countries** geo data appears (if you had it in Matomo)

#### Step 7: Once satisfied, import into production

```bash
# Import the same migration SQL into your production Umami
psql -h your-production-host -U user -d umami < migration.sql
```

The `ON CONFLICT DO NOTHING` clauses ensure this is safe to run even if some data already exists.

#### Resetting the local environment

If you need to start fresh:

```bash
# Stop and remove containers + volumes
docker-compose down -v

# Start fresh
docker-compose up -d
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

**"Unknown browser code"**: The migration maps unknown codes to the original value. Check if it's a newer browser not in the mapping.

**Duplicate key errors**: The SQL uses `ON CONFLICT DO NOTHING`, so duplicates are safely ignored. This is expected on re-runs.

**Memory issues**: Reduce `--batch-size` for large migrations, or split by date ranges.

**Missing referrers**: If action-level referrer is NULL, the tool falls back to visit-level referrer. Some pageviews may still have no referrer data.

## License

MIT License - see LICENSE file for details.
