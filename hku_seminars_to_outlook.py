import os
import sys
from datetime import datetime, timedelta
from urllib.parse import urljoin

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError as exc:  # pragma: no cover - fallback message
    raise SystemExit(
        "This script requires Python 3.9+ (zoneinfo module is missing)."
    ) from exc

import requests
from bs4 import BeautifulSoup

from email_notifier import SeminarEmailNotifier


HK_TZ = ZoneInfo("Asia/Hong_Kong")

HKU_SEMINAR_URL = "https://www.cs.hku.hk/programmes/research-based/mphil-phd-courses-offered"
SUBJECT_PREFIX = "[HKU CS Seminar] "


def parse_datetime_range(date_str: str, time_range_str: str):
    """
    输入:
        date_str: "November 21, 2025"
        time_range_str: "10:30 am - 11:30 am" 或 "11:00 am - 12:00 nn"
    返回:
        start_dt, end_dt (带 Asia/Hong_Kong 时区的 datetime)
    """
    date_str = date_str.strip()
    date = datetime.strptime(date_str, "%B %d, %Y").date()

    if not time_range_str:
        # 如果网页上没有时间，默认全天事件（一般不会发生）
        start_dt = datetime(date.year, date.month, date.day, 9, 0, tzinfo=HK_TZ)
        end_dt = start_dt + timedelta(hours=1)
        return start_dt, end_dt

    parts = time_range_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Unexpected time range format: {time_range_str}")

    def parse_time(t: str):
        t = t.strip().lower()
        # "12:00 nn" 处理成 12:00 pm
        t = t.replace("nn", "pm")
        t = t.replace(" noon", " pm")
        # 有的写法可能是 "10:00am" 中间没空格，统一加空格
        if "am" in t and " " not in t:
            t = t.replace("am", " am")
        if "pm" in t and " " not in t:
            t = t.replace("pm", " pm")
        meridiem = None
        if " am" in t:
            meridiem = "am"
        elif " pm" in t:
            meridiem = "pm"
        return datetime.strptime(t, "%I:%M %p").time(), meridiem

    start_time, start_meridiem = parse_time(parts[0])
    end_time, end_meridiem = parse_time(parts[1])

    start_dt = datetime.combine(date, start_time).replace(tzinfo=HK_TZ)
    end_dt = datetime.combine(date, end_time).replace(tzinfo=HK_TZ)
    if end_dt <= start_dt:
        if start_meridiem == "am" and end_meridiem == "am":
            end_dt = end_dt + timedelta(hours=12)
        elif start_meridiem == "pm" and end_meridiem == "am":
            end_dt = end_dt + timedelta(days=1)
        else:
            end_dt = end_dt + timedelta(hours=12)
    return start_dt, end_dt


def fetch_seminars():
    """
    从 HKU CS 网站抓取 seminars 表格，返回列表：
    [
        {
            "title": ...,
            "speaker": ...,
            "start": datetime,
            "end": datetime,
            "venue": ...
        },
        ...
    ]
    """
    resp = requests.get(HKU_SEMINAR_URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 找到 "Schedule of the seminars" 对应的 h2
    h2 = None
    for tag in soup.find_all("h2"):
        if "Schedule of the seminars" in tag.get_text():
            h2 = tag
            break

    if not h2:
        raise RuntimeError("Cannot find 'Schedule of the seminars' heading on the page.")

    table = h2.find_next("table")
    if not table:
        raise RuntimeError("Cannot find seminar table following the heading.")

    seminars = []
    rows = table.find_all("tr")
    if not rows:
        return seminars

    # 第一行是表头，跳过
    for tr in rows[1:]:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        # Title（可能包在 <a> 里）
        title_link = tds[0].find("a", href=True)
        title = tds[0].get_text(strip=True)
        link = (
            urljoin(HKU_SEMINAR_URL, title_link["href"])
            if title_link and title_link["href"]
            else None
        )
        # Speaker
        speaker = tds[1].get_text(strip=True)

        # Date and time 列：第一行是日期，第二行是时间范围
        date_time_parts = list(tds[2].stripped_strings)
        if not date_time_parts:
            continue
        date_str = date_time_parts[0]
        time_range_str = date_time_parts[1] if len(date_time_parts) > 1 else ""

        start_dt, end_dt = parse_datetime_range(date_str, time_range_str)

        # Venue
        venue = tds[3].get_text(strip=True)

        seminars.append(
            {
                "title": title,
                "speaker": speaker,
                "start": start_dt,
                "end": end_dt,
                "venue": venue,
                "link": link,
            }
        )

    return seminars


def print_seminar_overview(seminars):
    print("Seminar list:")
    for s in seminars:
        start_str = s["start"].strftime("%Y-%m-%d %H:%M")
        end_str = s["end"].strftime("%H:%M")
        print(
            f" - {s['title']} | {s['speaker']} | "
            f"{start_str}-{end_str} ({HK_TZ.key}) | {s['venue']}"
        )
    print(f"Total {len(seminars)} seminar(s).\n")


def sync_seminars_via_email():
    seminars = fetch_seminars()
    if not seminars:
        print("No seminars found on the page.")
        return

    now_hk = datetime.now(HK_TZ)
    upcoming = [s for s in seminars if s["end"] >= now_hk]
    if not upcoming:
        print("No upcoming seminars found.")
        return

    print(f"Found {len(seminars)} seminars on HKU page, {len(upcoming)} upcoming.")
    print_seminar_overview(upcoming)

    notifier = SeminarEmailNotifier.from_config_file(
        os.environ.get("HKU_CONFIG_PATH", "config.json"),
        tz=HK_TZ,
        source_url=HKU_SEMINAR_URL,
        subject_prefix=SUBJECT_PREFIX,
    )
    new_count = notifier.send_new_invites(upcoming)
    print(f"Completed. Sent {new_count} new invitation(s).")


if __name__ == "__main__":
    sync_seminars_via_email()
