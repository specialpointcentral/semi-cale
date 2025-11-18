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
- `from_email`: Sender address (defaults to `smtp_user` if left blank).
- `to_emails`: Recipients list (array or comma-separated string).
- `email_subject`: Optional fixed subject; defaults to “[HKU CS Seminar] …”.
- `state_file`: Path to the JSON file used to remember which seminars have been emailed.

## Notes

- Network access to `https://www.cs.hku.hk/programmes/research-based/mphil-phd-courses-offered` is required.
- SMTP service must allow sending `text/calendar` meeting requests (tested with Aliyun SMTP).
- To force a re-send of all seminars, delete `sent_seminars.json`.
