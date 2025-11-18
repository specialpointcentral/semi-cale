import json
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage


class SeminarEmailNotifier:
    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        to_emails: list[str],
        subject_override: str,
        use_starttls: bool,
        use_ssl: bool,
        state_file: str,
        tz,
        source_url: str,
        subject_prefix: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email or smtp_user
        self.to_emails = to_emails
        self.subject_override = subject_override
        self.use_starttls = use_starttls
        self.use_ssl = use_ssl
        self.state_file = state_file
        self.tz = tz
        self.source_url = source_url
        self.subject_prefix = subject_prefix

    @classmethod
    def from_config_file(cls, path: str, tz, source_url: str, subject_prefix: str):
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        to_emails = cfg.get("to_emails", [])
        if isinstance(to_emails, str):
            to_emails = [e.strip() for e in to_emails.split(",") if e.strip()]

        starttls_cfg = bool(cfg.get("smtp_starttls", True))
        use_ssl_cfg = bool(cfg.get("smtp_ssl", False))
        return cls(
            smtp_host=cfg.get("smtp_host", ""),
            smtp_port=int(cfg.get("smtp_port", 587)),
            smtp_user=cfg.get("smtp_user", ""),
            smtp_password=cfg.get("smtp_password", ""),
            from_email=cfg.get("from_email", ""),
            to_emails=to_emails,
            subject_override=cfg.get("email_subject", ""),
            use_starttls=starttls_cfg,
            use_ssl=use_ssl_cfg,
            state_file=cfg.get("state_file", "sent_seminars.json"),
            tz=tz,
            source_url=source_url,
            subject_prefix=subject_prefix,
        )

    def ensure_ready(self):
        if not self.smtp_host:
            raise RuntimeError("SMTP host is not configured. Set HKU_SMTP_HOST.")
        if not self.from_email:
            raise RuntimeError(
                "Sender email is empty. Set HKU_FROM_EMAIL or HKU_SMTP_USER."
            )
        if not self.to_emails:
            raise RuntimeError("Recipient list is empty. Set HKU_TO_EMAILS.")

    def send_new_invites(self, seminars: list[dict]) -> int:
        self.ensure_ready()
        sent = self._load_sent_keys()
        new_count = 0

        for seminar in seminars:
            key = self._event_key(seminar)
            if key in sent:
                continue

            msg = self._build_email_message(seminar)
            self._send_email(msg)
            sent.add(key)
            self._save_sent_keys(sent)  # flush per send to avoid losing progress
            new_count += 1
            print(
                f"Sent invite for: {seminar['title']} "
                f"({seminar['start']:%Y-%m-%d %H:%M})"
            )
        return new_count

    def _event_key(self, seminar):
        return (
            f"{seminar['title']}|{seminar['speaker']}|"
            f"{seminar['start'].isoformat()}"
        )

    def _load_sent_keys(self):
        if not os.path.exists(self.state_file):
            return set()
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Warning: failed to read {self.state_file}: {exc}")
            return set()

    def _save_sent_keys(self, keys):
        tmp_path = f"{self.state_file}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(sorted(keys), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.state_file)

    def _format_ics_datetime(self, dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _build_single_ics(self, seminar, dtstamp: str) -> str:
        uid = self._event_key(seminar) + "@hku-cs"
        dtstart = self._format_ics_datetime(seminar["start"])
        dtend = self._format_ics_datetime(seminar["end"])
        subject = f"{self.subject_prefix}{seminar['title']} — {seminar['speaker']}"
        description = (
            f"Speaker: {seminar['speaker']}\\n"
            f"Venue: {seminar['venue']}\\n"
            f"Source: {self.source_url}"
        )
        if seminar.get("link"):
            description += f"\\nPoster: {seminar['link']}"

        lines = [
            "BEGIN:VCALENDAR",
            "PRODID:-//HKU CS Seminar Sync//EN",
            "VERSION:2.0",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            "SEQUENCE:0",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            f"SUMMARY:{subject}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"LOCATION:{seminar['venue']}",
            f"DESCRIPTION:{description}",
            f"ORGANIZER;CN={self.from_email}:MAILTO:{self.from_email}",
        ]
        for attendee in self.to_emails:
            lines.append(
                "ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION;"
                f"ROLE=REQ-PARTICIPANT:MAILTO:{attendee}"
            )
        lines.extend(["PRIORITY:5", "CLASS:PUBLIC", "END:VEVENT", "END:VCALENDAR", ""])
        return "\r\n".join(lines)

    def _build_email_message(self, seminar: dict):
        dtstamp = self._format_ics_datetime(datetime.now(tz=timezone.utc))
        per_event_subject = (
            f"{self.subject_prefix}{seminar['title']} — {seminar['speaker']}"
        )
        msg = EmailMessage()
        msg["Subject"] = self.subject_override or per_event_subject
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)

        body = (
            f"{seminar['title']} — {seminar['speaker']}\n"
            f"Time: {seminar['start'].strftime('%Y-%m-%d %H:%M')} - "
            f"{seminar['end'].strftime('%H:%M')} ({self.tz.key})\n"
            f"Venue: {seminar['venue']}\n"
            f"Source: {self.source_url}\n"
        )
        if seminar.get("link"):
            body += f"Poster: {seminar['link']}\n"
        msg.set_content(body)

        rows_html = [
            f"<tr><td class='label'>Title</td><td class='value'>{seminar['title']}</td></tr>",
            f"<tr><td class='label'>Speaker</td><td class='value'>{seminar['speaker']}</td></tr>",
            f"<tr><td class='label'>Time</td><td class='value'>{seminar['start'].strftime('%Y-%m-%d %H:%M')} - {seminar['end'].strftime('%H:%M')} ({self.tz.key})</td></tr>",
            f"<tr><td class='label'>Venue</td><td class='value'>{seminar['venue']}</td></tr>",
            f"<tr><td class='label'>Source</td><td class='value'><a href='{self.source_url}'>{self.source_url}</a></td></tr>",
        ]
        if seminar.get("link"):
            rows_html.append(
                f"<tr><td class='label'>Poster</td><td class='value'><a href='{seminar['link']}'>{seminar['link']}</a></td></tr>"
            )

        html = f"""
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; color: #222; }}
    .card {{ max-width: 640px; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }}
    h2 {{ margin: 0 0 12px 0; font-size: 20px; color: #1a4d8f; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ padding: 8px 6px; vertical-align: top; }}
    .label {{ width: 80px; font-weight: bold; color: #555; }}
    .value {{ color: #222; }}
    a {{ color: #1a4d8f; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>{per_event_subject}</h2>
    <table>
      {''.join(rows_html)}
    </table>
  </div>
</body>
</html>
""".strip()
        msg.add_alternative(html, subtype="html")

        msg.make_mixed()
        ics_text = self._build_single_ics(seminar, dtstamp)
        cal_part = EmailMessage()
        cal_part.set_content(ics_text, subtype="calendar", charset="utf-8")
        cal_part.replace_header(
            "Content-Type",
            'text/calendar; method=REQUEST; charset="UTF-8"; name="invite.ics"',
        )
        cal_part.add_header("Content-Disposition", 'inline; filename="invite.ics"')
        msg.attach(cal_part)
        msg["Content-class"] = "urn:content-classes:calendarmessage"
        return msg


    def _send_email(self, msg: EmailMessage):
        smtp_class = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
        with smtp_class(self.smtp_host, self.smtp_port) as smtp:
            if self.use_starttls and not self.use_ssl:
                smtp.starttls()
            if self.smtp_user and self.smtp_password:
                smtp.login(self.smtp_user, self.smtp_password)
            smtp.send_message(msg)
