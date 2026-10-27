# Customer Signals

Django customer segmentation and action workflow with explainable purchase, engagement and service signals; effective-dated consent; action suppression; audited outcome transitions; data validation; synthetic-data generation; and streamed exports.

See [UI_STYLE_GUIDE.md](UI_STYLE_GUIDE.md) for the Customer Signals design tokens, components, typography, and motion rules.

## Local development

Requires Python 3.11+.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py setup_roles
python manage.py generate_demo
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. In development, workflow tasks run eagerly so Redis is not required. Create a local operator through `python manage.py createsuperuser`; login uses Django's username field. For a controlled bootstrap, set `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD` in the shell, then run `python manage.py bootstrap_admin`. The bootstrap command rejects passwords shorter than 12 characters. Secrets are read from environment variables and are never checked into the repository.

## Operator workflow

1. Create the role groups with `python manage.py setup_roles`, then assign users to groups in `/admin/`. Groups are System Administrators, Marketing Operations, Support Agents, and Analysts.
2. Inspect customer, order, product, engagement, support, consent, segment-rule, and action-catalog records. Consent records are append-only; add a new effective-dated decision to record a withdrawal or renewed permission.
3. Marketing Operations selects **Rebuild segments**. The job derives RFM/service/engagement values, snapshots the active rule, stores the rationale and leaves prior memberships as historical records.
4. Select **Run recommendations**. The job checks active segment/action dates, current channel consent, and cooldown. It writes each decision and an initial lifecycle event, including suppression reasons.
5. Marketing can preview pending email delivery with `python manage.py dispatch_actions`. Actual SMTP submission requires both `--send` and `ACTION_DELIVERY_ENABLED=true`. The dispatcher rechecks consent immediately before delivery, records attempts, and locks the customer during submission. SMS and push remain queued until their providers are configured.
6. Operators record `recommended → sent/suppressed → converted/not_converted` through the evaluation page. Support Agents update support cases through the customer profile. Invalid transitions are rejected; every accepted transition is an append-only event with actor, timestamp and notes.
7. Evaluation reports send/conversion/suppression counts and attributed revenue. Analysts and authorized operations users can stream action, customer, and membership CSV exports.
8. Run `python manage.py validate_data` and `python manage.py export_data`. Exports include streamed CSV and Django-fixture JSON for 13 domain entities, a row-count/SHA-256 manifest, a data-only SQL seed, and a separate `ground_truth.json`.

## Roles and access

- **System Administrators**: full Django admin and user/group configuration.
- **Marketing Operations**: review customers and rules, edit campaign configuration, run segmentation/recommendations, record action outcomes, export permitted data.
- **Support Agents**: view customer/order/consent context and create support-case status transitions with required reopen notes.
- **Analysts**: read-only views and exports; no workflow execution or data mutation.

The dashboard, customer directory, profile, evaluation, transition forms, and exports require login and model permissions. Django admin status fields for consent, orders, memberships, outcomes, and support cases are read-only where history must be retained. `/health/live` checks process availability; `/health/ready` checks the database and (in production mode) the task broker.

## Segmentation rules

Rules are deterministic and evaluated in this precedence order: new customer → no completed purchase in 180+ days → $1,000+ net completed spend across at least 3 orders → support case with service cost at least $100 → 2+ engagement events in the last 30 days → active. Returns and cancellations are excluded from RFM. Each membership snapshots its rule definition and stores score and reason. Conflicting exclusive segment memberships are reported as a ground-truth anomaly; the production segment service assigns one current membership per customer.

## Full-scale synthetic data

`python manage.py generate_demo` generates the starter scale with seed `20261022`. `--customers`, `--orders`, `--events`, and `--seed` parameterize the same generator. `--full` generates 50,000 customers, 200,000 orders, and 1,000,000 engagement events with bounded batches. The default generator intentionally injects four labeled anomalies after baseline rows: conflicting exclusive memberships, an action sent against consent, a returned order whose gross amount remains positive, and a mismatched action attribution. These rows are synthetic acceptance fixtures; never run this generator or its `--clear` option against a production database.

To run the full synthetic acceptance volume in an isolated SQLite database on Windows:

```powershell
$env:DJANGO_DB_NAME = "data/full-scale-check/db.sqlite3"
python manage.py migrate
python manage.py setup_roles
python manage.py generate_demo --full --output data/full-scale-check/generated
python manage.py shell -c "from segments.services import rebuild_segments, run_recommendations; print(rebuild_segments()); print(run_recommendations())"
python manage.py validate_data --output data/full-scale-check/validation_summary.json --ground-truth data/full-scale-check/generated/ground_truth.json
python manage.py export_data --output data/full-scale-check/export --generation-manifest data/full-scale-check/generated/generation_manifest.json
Remove-Item Env:DJANGO_DB_NAME
```

The SQLite full-scale run is a deterministic acceptance check, not a substitute for PostgreSQL capacity testing. Do not add `--clear` to a database with user or customer data.

## Production deployment

The production profile uses PostgreSQL, Redis, Celery workers, Gunicorn, WhiteNoise static assets, secure cookies/HSTS, required secret configuration, health checks, and a non-root app container. TLS must terminate at a trusted reverse proxy/load balancer; restrict access to the app's loopback port and configure the proxy to overwrite `X-Forwarded-Proto`.

1. Copy `.env.example` to `.env`; generate unique values for `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, and the bootstrap administrator. Use URL-safe database/Redis passwords or percent-encode reserved URL characters.
2. Set the real host and HTTPS CSRF origin. Configure email SMTP only after approval; keep `ACTION_DELIVERY_ENABLED=false` until the mail route is approved.
3. Start with `docker compose up --build -d`. The web entrypoint applies migrations, prepares role groups, bootstraps the administrator from environment, collects static files, and runs Django's deployment checks. The worker runs Celery separately.
4. Point a TLS proxy at `127.0.0.1:8000`, expose `/health/ready` only to infrastructure checks, and back up PostgreSQL and Redis persistent volumes.
5. Monitor application/worker stdout, PostgreSQL backups, Redis persistence, failed `WorkflowRun` records, and delivery attempt events. Size Gunicorn/Celery concurrency and database connections to the host; do not use SQLite in production.

The Compose stack does not provision TLS certificates, cloud secrets management, backups, or an SMS/push provider. These must be supplied by the deployment environment. Email delivery is at-least-once from SMTP's perspective; use an idempotent provider adapter if exactly-once delivery is required.

## Schema, provenance and exports

See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for field definitions, types, allowed values, cardinalities, lifecycle, effective dates and validation rules. All generated names, addresses (`example.test`), transactions, events and preferences are synthetic; no external data is used. `ground_truth.json` is separate from analytical features. `seed.sql` contains only domain table data and omits security users/credentials; apply Django migrations first.

CSV/JSON exports are streamed and ordered by primary key to bound memory and stabilize checksums. PostgreSQL exports include portable data-only SQL inserts; import only after the matching migrations and into an empty database. Operator/user records are excluded from the seed.

## Verification

```powershell
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py validate_data
```
