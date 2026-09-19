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


def prev_year_range(iso_date: str | None = None) -> tuple[str, str]:
    d = date.fromisoformat(iso_date[:10]) if iso_date else date.today()
    start = date(d.year - 1, 1, 1)
    end = date(d.year - 1, 12, 31)
    return start.isoformat(), end.isoformat()
