import sys
from datetime import datetime, timedelta

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError as exc:  # pragma: no cover - fallback message
    raise SystemExit(
        "This script requires Python 3.9+ (zoneinfo module is missing)."
    ) from exc

import requests
from bs4 import BeautifulSoup
import msal


HK_TZ = ZoneInfo("Asia/Hong_Kong")

HKU_SEMINAR_URL = "https://www.cs.hku.hk/programmes/research-based/mphil-phd-courses-offered"
SUBJECT_PREFIX = "[HKU CS Seminar] "

# Azure AD 应用的 Client ID（在 Azure Portal App registrations 里看到）
# 一定要改成你自己的 App 的 client_id
CLIENT_ID = "YOUR_CLIENT_ID_HERE"

# 一般设置为 common 就可以支持个人/企业账号，
# 如果你有固定 tenant 也可以改成对应 tenant id
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["offline_access", "Calendars.ReadWrite"]

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


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
        return datetime.strptime(t, "%I:%M %p").time()

    start_time = parse_time(parts[0])
    end_time = parse_time(parts[1])

    start_dt = datetime.combine(date, start_time).replace(tzinfo=HK_TZ)
    end_dt = datetime.combine(date, end_time).replace(tzinfo=HK_TZ)
    return start_dt, end_dt


def acquire_token():
    """
    通过 device code 登录获取 Graph access token。
    第一次运行会让你在浏览器里登录，以后可复用缓存（这里用的是内存缓存，每次启动需要再登录一次）。
    """
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    accounts = app.get_accounts()
    result = None

    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(
                "Failed to create device flow. Check your CLIENT_ID and network."
            )
        print(flow["message"])
        sys.stdout.flush()
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise RuntimeError(
            f"Token acquisition failed: {result.get('error_description', result)}"
        )

    return result["access_token"]


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
        title = tds[0].get_text(strip=True)
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
            }
        )

    return seminars


def get_calendar_events_in_range(token, start_dt, end_dt):
    """
    从 Outlook 默认日历获取指定时间范围内的所有事件。
    使用 /me/calendar/calendarView 接口。
    """
    headers = {"Authorization": f"Bearer {token}"}

    # Graph 要求 start/end 用 ISO8601，推荐用 UTC
    start_utc = start_dt.astimezone(ZoneInfo("UTC")).isoformat()
    end_utc = end_dt.astimezone(ZoneInfo("UTC")).isoformat()

    params = {
        "startDateTime": start_utc,
        "endDateTime": end_utc,
        "$top": "1000",
    }

    events = []
    url = f"{GRAPH_BASE}/me/calendar/calendarView"

    while True:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        events.extend(data.get("value", []))

        next_link = data.get("@odata.nextLink")
        if not next_link:
            break
        # nextLink 里已经包含了所有 query 参数，所以后续请求不需要再传 params
        url = next_link
        params = None

    return events


def parse_graph_datetime(dt_str: str):
    """
    把 Graph 返回的 dateTime 字符串解析成带 Asia/Hong_Kong 时区的 datetime。
    这里假设我们创建时就是香港时间，本地比较也统一按香港时间。
    """
    if not dt_str:
        return None

    # 可能是 "2025-11-21T10:30:00.0000000" 或 "2025-11-21T10:30:00.0000000Z"
    s = dt_str.replace("Z", "")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=HK_TZ)
    else:
        dt = dt.astimezone(HK_TZ)
    return dt


def build_existing_event_index(events):
    """
    从一批 events 中筛选出我们脚本创建的 seminars（subject 有前缀），
    返回:
      index: {(subject, start_truncated): event}
      seminar_events: [event, ...]  # 仅我们的 events
    """
    index = {}
    seminar_events = []

    for e in events:
        subject = e.get("subject", "") or ""
        if not subject.startswith(SUBJECT_PREFIX):
            continue

        start_info = e.get("start", {})
        start_dt = parse_graph_datetime(start_info.get("dateTime"))
        if not start_dt:
            continue

        key = (subject, start_dt.replace(second=0, microsecond=0))
        index[key] = e
        seminar_events.append(e)

    return index, seminar_events


def create_event(token, seminar):
    """
    创建单个 seminar 的 Outlook 事件。
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    subject = f"{SUBJECT_PREFIX}{seminar['title']} — {seminar['speaker']}"

    body_html = (
        f"<p><strong>{seminar['title']}</strong></p>"
        f"<p>Speaker: {seminar['speaker']}</p>"
        f"<p>Venue: {seminar['venue']}</p>"
        f"<p>Source: <a href='{HKU_SEMINAR_URL}'>{HKU_SEMINAR_URL}</a></p>"
    )

    payload = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
        "start": {
            "dateTime": seminar["start"].isoformat(),
            "timeZone": "Asia/Hong_Kong",
        },
        "end": {
            "dateTime": seminar["end"].isoformat(),
            "timeZone": "Asia/Hong_Kong",
        },
        "location": {"displayName": seminar["venue"]},
    }

    resp = requests.post(f"{GRAPH_BASE}/me/events", headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()


def delete_event(token, event_id: str):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_BASE}/me/events/{event_id}"
    resp = requests.delete(url, headers=headers)
    # Graph 对已删除 / 不存在的 event 可能返回 204 或 404，
    # 这里简单忽略 404 错误
    if resp.status_code not in (204, 404):
        resp.raise_for_status()


def sync_seminars_to_outlook():
    # 1. 抓取网页上的所有 seminar
    seminars = fetch_seminars()
    if not seminars:
        print("No seminars found on the page.")
        return

    print(f"Found {len(seminars)} seminars on HKU page.")

    # 2. 获取 Graph token
    token = acquire_token()

    # 3. 获取一个稍微宽一点的时间范围内的已有事件
    earliest = min(s["start"] for s in seminars) - timedelta(days=7)
    latest = max(s["end"] for s in seminars) + timedelta(days=7)

    events = get_calendar_events_in_range(token, earliest, latest)
    existing_index, seminar_events = build_existing_event_index(events)

    # 4. 去重后创建新的事件
    created = 0
    for s in seminars:
        subject = f"{SUBJECT_PREFIX}{s['title']} — {s['speaker']}"
        key = (subject, s["start"].replace(second=0, microsecond=0))

        if key in existing_index:
            # 已经存在，不重复创建
            continue

        create_event(token, s)
        created += 1

    # 5. 删除过期的 seminar 事件（只删我们自己创建的）
    now_hk = datetime.now(HK_TZ)
    deleted = 0
    for e in seminar_events:
        end_info = e.get("end", {})
        end_dt = parse_graph_datetime(end_info.get("dateTime"))
        if end_dt and end_dt < now_hk:
            delete_event(token, e["id"])
            deleted += 1

    print(f"Created {created} new events, deleted {deleted} expired events.")


if __name__ == "__main__":
    sync_seminars_to_outlook()

