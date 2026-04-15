from datetime import date


def month_range(ref: date) -> tuple[date, date]:
    """Return (month_start, next_month_start) for the month containing ref.

    month_start is the first day of ref's month.
    next_month_start is the first day of the following month.
    """
    month_start = ref.replace(day=1)
    if ref.month == 12:
        next_month_start = date(ref.year + 1, 1, 1)
    else:
        next_month_start = date(ref.year, ref.month + 1, 1)
    return month_start, next_month_start


def prev_month_range(ref: date) -> tuple[date, date]:
    """Return (prev_month_start, month_start) for the month before ref's month.

    prev_month_start is the first day of the previous month.
    month_start is the first day of ref's month.
    """
    month_start = ref.replace(day=1)
    if month_start.month == 1:
        prev_month_start = date(month_start.year - 1, 12, 1)
    else:
        prev_month_start = date(month_start.year, month_start.month - 1, 1)
    return prev_month_start, month_start


def next_month_range(ref: date) -> tuple[date, date]:
    """Return (next_month_start, month_after_next_start) for the month after ref's month.

    next_month_start is the first day of the following month.
    month_after_next_start is the first day of the month after that.
    """
    if ref.month == 12:
        next_month_start = date(ref.year + 1, 1, 1)
        if next_month_start.month == 12:
            month_after_next_start = date(next_month_start.year + 1, 1, 1)
        else:
            month_after_next_start = date(
                next_month_start.year, next_month_start.month + 1, 1
            )
    else:
        next_month_start = date(ref.year, ref.month + 1, 1)
        if next_month_start.month == 12:
            month_after_next_start = date(next_month_start.year + 1, 1, 1)
        else:
            month_after_next_start = date(
                next_month_start.year, next_month_start.month + 1, 1
            )
    return next_month_start, month_after_next_start
