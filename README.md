# HKU Seminar Email Sync

This script scrapes the HKU CS research programme seminar table and sends Outlook-compatible meeting invitations via SMTP. Upcoming events are batched into a single email with an inline ICS so recipients can add every seminar to their calendar at once.

## Quick Start

1. **Install Python 3.9+** (needed for `zoneinfo`).
2. **Copy the default config** and edit it with your SMTP credentials and recipients:
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
   The script prints upcoming seminars, then sends a single calendar invite email if there are new events that haven’t been mailed before (`sent_seminars.json` tracks deduplication).

## Configuration fields

- `smtp_host`, `smtp_port`, `smtp_ssl`, `smtp_starttls`: SMTP connection settings.
- `smtp_user`, `smtp_password`: SMTP credentials (password can be an app password).
- `sender_email`: Optional `Sender` header value, e.g. `"HKU CS Seminar Bot <example@example.com>"`. If omitted, falls back to `smtp_user`.
- `from_email`: Logical organizer / From address (defaults to `smtp_user` if left blank). Supports `"Name <email>"` format.
- `to_emails`: Recipients list (array or comma-separated string).
- `email_subject`: Optional fixed subject; defaults to “[HKU CS Seminar] …”.
- `state_file`: Path to the JSON file used to remember which seminars have been emailed.

## Notes

- Network access to `https://www.cs.hku.hk/programmes/research-based/mphil-phd-courses-offered` is required.
- SMTP service must allow sending `text/calendar` meeting requests (tested with Aliyun SMTP).
- To force a re-send of all seminars, delete `sent_seminars.json`.

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
