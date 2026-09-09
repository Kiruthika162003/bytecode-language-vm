"""Civil dates: calendar arithmetic on whole days, with no clock and no zones.

This library handles dates and refuses to handle times, and the refusal is the design
rather than an omission. A date is a position on the civil calendar, a year, a month
and a day, and arithmetic on it is exact: the number of days between two dates is a
whole number that every implementation agrees on. The moment a clock enters, so do
zones, offsets that change twice a year, leap seconds, and the question of which day it
is somewhere else, and every one of those needs a database of political decisions that
gets stale. A library that answered date questions correctly and time questions
approximately would be worse than one that answers only what it can answer exactly, so
there is no now, no current date, and no time of day here at all. A program that needs
the current date gets it from outside and passes it in.

Everything is computed from one primitive: the count of days from a fixed epoch, taken
here as the first of January in the year one. Converting a date to that count and back
turns every other question into arithmetic on integers. The difference between two
dates is a subtraction. Adding a month is the one operation that is not, because months
have different lengths, and the convention chosen is to clamp: a month added to the
thirty first of January gives the twenty eighth or twenty ninth of February rather than
overflowing into March. Clamping is what people mean by the same day next month, and it
has the consequence, worth knowing, that adding a month twice is not always the same as
adding two months.

Leap years follow the Gregorian rule everywhere, including for years before the
calendar existed, which is the proleptic convention: the arithmetic stays uniform and
a date in the year 1500 is interpreted as if the reform had already happened, which it
had not. Anyone doing history with this library needs to know that, and it is recorded
here rather than left to surprise them.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_MONTH_LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _whole(value: Any, who: str, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(
            f"{who} needs a whole number for the {what}, not a {type_name(value)}"
        )
    return value


def is_leap(year: int) -> bool:
    """The Gregorian rule, applied to every year including those before the reform."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    if month == 2 and is_leap(year):
        return 29
    return _MONTH_LENGTHS[month - 1]


def _check_date(year: int, month: int, day: int, who: str) -> None:
    if year < 1:
        raise Arithmetic(
            f"{who} counts years from one, so {year} is before the calendar starts"
        )
    if not 1 <= month <= 12:
        raise Arithmetic(f"{who} needs a month from 1 to 12, not {month}")
    longest = days_in_month(year, month)
    if not 1 <= day <= longest:
        raise Arithmetic(
            f"{who} was given day {day} of month {month} in {year}, which has "
            f"only {longest} days"
        )


def to_days(year: int, month: int, day: int) -> int:
    """Days from the first of January in year one, which every other answer builds on."""
    total = 0
    for past in range(1, year):
        total += 366 if is_leap(past) else 365
    for past in range(1, month):
        total += days_in_month(year, past)
    return total + day - 1


def from_days(count: int) -> tuple[int, int, int]:
    if count < 0:
        raise Arithmetic(f"a day count cannot be negative, but was given {count}")
    year = 1
    while True:
        length = 366 if is_leap(year) else 365
        if count < length:
            break
        count -= length
        year += 1
    month = 1
    while count >= days_in_month(year, month):
        count -= days_in_month(year, month)
        month += 1
    return year, month, count + 1


def _triple(value: Any, who: str) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        raise TypeMismatch(
            f"{who} needs a date as a list of three numbers, the year, the month and "
            f"the day, not a {type_name(value)}"
        )
    year = _whole(value[0], who, "year")
    month = _whole(value[1], who, "month")
    day = _whole(value[2], who, "day")
    _check_date(year, month, day, who)
    return year, month, day


def _date_of(args: list[Any]) -> list[int]:
    year = _whole(args[0], "date", "year")
    month = _whole(args[1], "date", "month")
    day = _whole(args[2], "date", "day")
    _check_date(year, month, day, "date")
    return [year, month, day]


def _is_leap_year(args: list[Any]) -> bool:
    return is_leap(_whole(args[0], "isLeapYear", "year"))


def _month_length(args: list[Any]) -> int:
    year = _whole(args[0], "monthLength", "year")
    month = _whole(args[1], "monthLength", "month")
    if not 1 <= month <= 12:
        raise Arithmetic(f"monthLength needs a month from 1 to 12, not {month}")
    return days_in_month(year, month)


def _day_number(args: list[Any]) -> int:
    year, month, day = _triple(args[0], "dayNumber")
    return to_days(year, month, day)


def _date_from_number(args: list[Any]) -> list[int]:
    count = _whole(args[0], "dateFromNumber", "day count")
    year, month, day = from_days(count)
    return [year, month, day]


def _days_between(args: list[Any]) -> int:
    first = _triple(args[0], "daysBetween")
    second = _triple(args[1], "daysBetween")
    return to_days(*second) - to_days(*first)


def _add_days(args: list[Any]) -> list[int]:
    year, month, day = _triple(args[0], "addDays")
    count = _whole(args[1], "addDays", "day count")
    moved = to_days(year, month, day) + count
    if moved < 0:
        raise Arithmetic(
            f"addDays moved {count} days from {year}-{month}-{day}, which lands "
            "before the calendar starts"
        )
    return list(from_days(moved))


def _add_months(args: list[Any]) -> list[int]:
    year, month, day = _triple(args[0], "addMonths")
    count = _whole(args[1], "addMonths", "month count")
    total = (year * 12 + month - 1) + count
    if total < 0:
        raise Arithmetic("addMonths landed before the calendar starts")
    new_year = total // 12
    new_month = total % 12 + 1
    if new_year < 1:
        raise Arithmetic("addMonths landed before the calendar starts")
    # clamping, which is what people mean by the same day next month, and the reason
    # adding a month twice is not always the same as adding two months
    return [new_year, new_month, min(day, days_in_month(new_year, new_month))]


def _add_years(args: list[Any]) -> list[int]:
    year, month, day = _triple(args[0], "addYears")
    count = _whole(args[1], "addYears", "year count")
    moved = year + count
    if moved < 1:
        raise Arithmetic("addYears landed before the calendar starts")
    return [moved, month, min(day, days_in_month(moved, month))]


def _weekday(args: list[Any]) -> int:
    """One for Monday through seven for Sunday, since the epoch fell on a Monday."""
    year, month, day = _triple(args[0], "weekday")
    return to_days(year, month, day) % 7 + 1


def _weekday_name(args: list[Any]) -> str:
    return _DAY_NAMES[_weekday(args) - 1]


def _month_name(args: list[Any]) -> str:
    year, month, day = _triple(args[0], "monthName")
    del year, day
    return _MONTH_NAMES[month - 1]


def _day_of_year(args: list[Any]) -> int:
    year, month, day = _triple(args[0], "dayOfYear")
    return to_days(year, month, day) - to_days(year, 1, 1) + 1


def _week_of_year(args: list[Any]) -> int:
    year, month, day = _triple(args[0], "weekOfYear")
    return (_day_of_year([[year, month, day]]) - 1) // 7 + 1


def _is_weekend(args: list[Any]) -> bool:
    return _weekday(args) >= 6


def _format_date(args: list[Any]) -> str:
    year, month, day = _triple(args[0], "formatDate")
    return f"{year:04d}-{month:02d}-{day:02d}"


def _long_date(args: list[Any]) -> str:
    year, month, day = _triple(args[0], "longDate")
    named = _DAY_NAMES[_weekday([[year, month, day]]) - 1]
    return f"{named} {day} {_MONTH_NAMES[month - 1]} {year}"


def _parse_date(args: list[Any]) -> list[int]:
    text = args[0]
    if not isinstance(text, str):
        raise TypeMismatch(f"parseDate needs a string, not a {type_name(text)}")
    pieces = text.split("-")
    if len(pieces) != 3:
        raise Arithmetic(
            f"parseDate reads a date written as year-month-day, so it cannot read {text!r}"
        )
    try:
        year, month, day = (int(piece) for piece in pieces)
    except ValueError as bad:
        raise Arithmetic(f"parseDate found something that is not a number in {text!r}") from bad
    _check_date(year, month, day, "parseDate")
    return [year, month, day]


def _is_before(args: list[Any]) -> bool:
    return to_days(*_triple(args[0], "isBefore")) < to_days(*_triple(args[1], "isBefore"))


def _same_date(args: list[Any]) -> bool:
    return _triple(args[0], "sameDate") == _triple(args[1], "sameDate")


def _easter_of(args: list[Any]) -> list[int]:
    """The Gregorian computus: the date of Easter, by the anonymous algorithm.

    This was written from memory the first time and was wrong for every year it was
    checked against, by between one and five days, which is the useful kind of wrong:
    a computus that is close is indistinguishable from one that is right until someone
    compares it with a calendar. The version here is the anonymous Gregorian algorithm
    and it is checked against published dates in the tests rather than trusted, because
    nothing about the arithmetic reveals its own correctness on inspection.
    """
    year = _whole(args[0], "easter", "year")
    if year < 1:
        raise Arithmetic(f"easter counts years from one, so {year} has no answer")
    golden = year % 19
    century = year // 100
    within = year % 100
    leap_centuries = century // 4
    century_rest = century % 4
    lunar_shift = (century + 8) // 25
    lunar_correction = (century - lunar_shift + 1) // 3
    epact = (19 * golden + century - leap_centuries - lunar_correction + 15) % 30
    leap_years = within // 4
    year_rest = within % 4
    offset = (32 + 2 * century_rest + 2 * leap_years - epact - year_rest) % 7
    correction = (golden + 11 * epact + 22 * offset) // 451
    total = epact + offset - 7 * correction + 114
    return [year, total // 31, total % 31 + 1]


_REGISTRY: dict[str, tuple[int, Any]] = {
    "date": (3, _date_of),
    "isLeapYear": (1, _is_leap_year),
    "monthLength": (2, _month_length),
    "dayNumber": (1, _day_number),
    "dateFromNumber": (1, _date_from_number),
    "daysBetween": (2, _days_between),
    "addDays": (2, _add_days),
    "addMonths": (2, _add_months),
    "addYears": (2, _add_years),
    "weekday": (1, _weekday),
    "weekdayName": (1, _weekday_name),
    "monthName": (1, _month_name),
    "dayOfYear": (1, _day_of_year),
    "weekOfYear": (1, _week_of_year),
    "isWeekend": (1, _is_weekend),
    "formatDate": (1, _format_date),
    "longDate": (1, _long_date),
    "parseDate": (1, _parse_date),
    "isBefore": (2, _is_before),
    "sameDate": (2, _same_date),
    "easter": (1, _easter_of),
}


def install_date_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def date_names() -> list[str]:
    return sorted(_REGISTRY)
