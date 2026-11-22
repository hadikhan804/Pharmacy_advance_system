from __future__ import annotations

from datetime import date, datetime, timedelta


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return date.today().isoformat()


def add_days(iso_date: str, days: int) -> str:
    d = date.fromisoformat(iso_date[:10])
    return (d + timedelta(days=days)).isoformat()


def week_start(iso_date: str | None = None) -> str:
    d = date.fromisoformat(iso_date[:10]) if iso_date else date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def month_start(iso_date: str | None = None) -> str:
    d = date.fromisoformat(iso_date[:10]) if iso_date else date.today()
    return d.replace(day=1).isoformat()


def year_start(iso_date: str | None = None) -> str:
    d = date.fromisoformat(iso_date[:10]) if iso_date else date.today()
    return d.replace(month=1, day=1).isoformat()


def prev_month_range(iso_date: str | None = None) -> tuple[str, str]:
    d = date.fromisoformat(iso_date[:10]) if iso_date else date.today()
    first_this = d.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


def month_end(iso_date: str | None = None) -> str:
    d = date.fromisoformat(iso_date[:10]) if iso_date else date.today()
    if d.month == 12:
        nxt = date(d.year + 1, 1, 1)
    else:
        nxt = date(d.year, d.month + 1, 1)
    return (nxt - timedelta(days=1)).isoformat()


def iter_weeks(start: str, end: str) -> list[tuple[str, str]]:
    cur = date.fromisoformat(week_start(start))
    last = date.fromisoformat(end[:10])
    out = []
    while cur <= last:
        wend = cur + timedelta(days=6)
        out.append((cur.isoformat(), min(wend, last).isoformat()))
        cur = wend + timedelta(days=1)
    return out


def iter_months(start: str, end: str) -> list[tuple[str, str]]:
    cur = date.fromisoformat(month_start(start))
    last = date.fromisoformat(end[:10])
    out = []
    while cur <= last:
        mend = date.fromisoformat(month_end(cur.isoformat()))
        out.append((cur.isoformat(), min(mend, last).isoformat()))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


def iter_years(start: str, end: str) -> list[tuple[str, str]]:
    cur = date.fromisoformat(year_start(start))
    last = date.fromisoformat(end[:10])
    out = []
    while cur <= last:
        yend = date(cur.year, 12, 31)
        out.append((cur.isoformat(), min(yend, last).isoformat()))
        cur = date(cur.year + 1, 1, 1)
    return out


def prev_year_range(iso_date: str | None = None) -> tuple[str, str]:
    d = date.fromisoformat(iso_date[:10]) if iso_date else date.today()
    start = date(d.year - 1, 1, 1)
    end = date(d.year - 1, 12, 31)
    return start.isoformat(), end.isoformat()
