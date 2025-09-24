from datetime import datetime, timedelta, timezone

# We assume that the current timezone is UTC.
# This is also enforced by setting TZ=UTC in `main.py`


def get_first_date() -> datetime:
    return datetime(2022, 12, 26)


def get_week_ago(num_week_ago: int) -> datetime:
    return get_current_datetime() - timedelta(days=7 * num_week_ago)


def get_next_weekday_midnight(date: datetime, weekday: int) -> datetime:
    num_days = (weekday - date.weekday()) % 7
    if num_days == 0:
        num_days = 7
    next_weekday = date + timedelta(days=num_days)
    next_weekday = next_weekday.replace(hour=0, minute=0, second=0, microsecond=0)
    return next_weekday


def get_current_datetime() -> datetime:
    return get_next_weekday_midnight(datetime.now(timezone.utc), 3)


def get_seconds_until_reminder() -> float:
    now = datetime.now(timezone.utc)
    next_wednesday = get_next_weekday_midnight(now, 2)
    seconds_until_next_wednesday = (next_wednesday - now).total_seconds()
    return seconds_until_next_wednesday


def get_string_for_week(time: datetime, show_year: bool) -> str:
    # GPQ scores are due on Wednesdays
    # Any score submitted between one Wednesday and the next belongs to the upcoming Wednesday

    if show_year:
        # Use full 4-digit year and zero-padded month/day for consistency
        return f"{time.month:02d}/{time.day:02d}/{time.year}"

    return f"{time.month}/{time.day}"


def get_current_week() -> str:
    current = get_current_datetime()
    return get_string_for_week(current, True)


def get_last_week() -> str:
    last = get_week_ago(1)
    return get_string_for_week(last, True)
