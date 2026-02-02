# HKU Seminar Email Sync

This script scrapes the HKU CS research programme seminar table and sends Outlook-compatible meeting invitations via SMTP. Upcoming events are batched into a single email with an inline ICS so recipients can add every seminar to their calendar at once.

## Quick Start

1. **Install Python 3.9+** (needed for `zoneinfo`).
2. **Configure via environment variables or config file**:
   
   **Option A: Environment Variables** (recommended for CI/CD)
   ```bash
   export HKU_SMTP_HOST="smtp.example.com"
   export HKU_SMTP_PORT="587"
   export HKU_SMTP_SSL="false"
   export HKU_SMTP_STARTTLS="true"
   export HKU_SMTP_USER="example@example.com"
   export HKU_SMTP_PASSWORD="your_password"
   export HKU_FROM_EMAIL="Sender <example@example.com>"
   export HKU_TO_EMAILS="recipient1@example.com,recipient2@example.com"
   # Optional: HKU_SENDER_EMAIL, HKU_EMAIL_SUBJECT, HKU_STATE_FILE
   ```
   
   **Option B: Config File** (fallback if environment variables not set)
   ```bash
   cp config.json.default config.json
   # edit config.json with your SMTP password, recipients, etc.
   ```
   The file is ignored by git, so you can safely store secrets there.  
   Set `HKU_CONFIG_PATH=/path/to/config.json` if you store it elsewhere.
3. **Run the sync script** (creates/uses `.venv`, installs deps, runs scraper + email):
   ```bash
   ./run_hku_seminar_sync.sh
   ```
   The script prints upcoming seminars, then sends a single calendar invite email if there are new events that haven't been mailed before (`sent_seminars.json` tracks deduplication).

## Configuration fields

Configuration can be provided via environment variables (prefixed with `HKU_`) or via config file:

- `smtp_host` / `HKU_SMTP_HOST`: SMTP server hostname
- `smtp_port` / `HKU_SMTP_PORT`: SMTP server port
- `smtp_ssl` / `HKU_SMTP_SSL`: Use SSL connection (true/false)
- `smtp_starttls` / `HKU_SMTP_STARTTLS`: Use STARTTLS (true/false)
- `smtp_user` / `HKU_SMTP_USER`: SMTP username
- `smtp_password` / `HKU_SMTP_PASSWORD`: SMTP password (can be an app password)
- `sender_email` / `HKU_SENDER_EMAIL`: Optional `Sender` header value, e.g. `"HKU CS Seminar Bot <example@example.com>"`. If omitted, falls back to `smtp_user`.
- `from_email` / `HKU_FROM_EMAIL`: Logical organizer / From address (defaults to `smtp_user` if left blank). Supports `"Name <email>"` format.
- `to_emails` / `HKU_TO_EMAILS`: Recipients list (array in JSON or comma-separated string in env vars)
- `email_subject` / `HKU_EMAIL_SUBJECT`: Optional fixed subject; defaults to "[HKU CS Seminar] …"
- `state_file` / `HKU_STATE_FILE`: Path to the JSON file used to remember which seminars have been emailed

**Priority**: Environment variables take precedence over config file if both are present.

## GitHub Actions Scheduled Sync

This repository includes a GitHub Actions workflow that automatically runs the seminar sync every hour. To set it up:

1. Go to your repository's **Settings** > **Secrets and variables** > **Actions**
2. Add the following secrets:
   - `HKU_SMTP_HOST`: SMTP server hostname (e.g., smtp.example.com)
   - `HKU_SMTP_PORT`: SMTP server port (e.g., 587)
   - `HKU_SMTP_SSL`: Use SSL connection (true/false)
   - `HKU_SMTP_STARTTLS`: Use STARTTLS (true/false)
   - `HKU_SMTP_USER`: SMTP username
   - `HKU_SMTP_PASSWORD`: SMTP password
   - `HKU_FROM_EMAIL`: Sender email address
   - `HKU_TO_EMAILS`: Comma-separated list of recipient emails
   - Optional: `HKU_SENDER_EMAIL`, `HKU_EMAIL_SUBJECT`, `HKU_STATE_FILE`

3. The workflow will run automatically every hour, or you can trigger it manually from the Actions tab.

The workflow file is located at `.github/workflows/seminar-sync.yml`.

## Notes

- Network access to `https://www.cs.hku.hk/programmes/research-based/mphil-phd-courses-offered` is required.
- SMTP service must allow sending `text/calendar` meeting requests (tested with Aliyun SMTP).
- To force a re-send of all seminars, delete `sent_seminars.json`.
