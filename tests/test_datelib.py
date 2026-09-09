from __future__ import annotations

import datetime

import pytest

from ember.datelib import (
    _easter_of,
    date_names,
    days_in_month,
    from_days,
    is_leap,
    to_days,
)
from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "date" in date_names()
        assert "daysBetween" in date_names()

    def test_the_names_are_sorted(self):
        assert date_names() == sorted(date_names())

    def test_there_are_twenty_one_of_them(self):
        assert len(date_names()) == 21

    def test_there_is_no_way_to_ask_for_now(self):
        # a date library with a clock needs a zone database that goes stale
        assert not any("now" in name.lower() for name in date_names())
        assert not any("time" in name.lower() for name in date_names())


class TestLeapYears:
    @pytest.mark.parametrize("year", [2000, 2004, 2020, 2024, 1600])
    def test_a_leap_year_is_recognised(self, year):
        assert is_leap(year)

    @pytest.mark.parametrize("year", [1900, 2100, 2023, 2025, 1700])
    def test_a_common_year_is_recognised(self, year):
        assert not is_leap(year)

    def test_a_century_is_not_a_leap_year_unless_divisible_by_four_hundred(self):
        assert not is_leap(1900)
        assert is_leap(2000)

    def test_february_has_an_extra_day_in_a_leap_year(self):
        assert days_in_month(2024, 2) == 29
        assert days_in_month(2023, 2) == 28

    def test_a_program_can_ask(self):
        assert evaluate("isLeapYear(2024)") == "true"

    def test_a_program_can_ask_a_month_length(self):
        assert evaluate("monthLength(2024, 2)") == "29"

    def test_a_month_out_of_range_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print monthLength(2024, 13);")


class TestAgainstTheHostCalendar:
    @pytest.mark.parametrize(
        "year,month,day",
        [
            (1, 1, 1),
            (1000, 6, 15),
            (1900, 2, 28),
            (2000, 2, 29),
            (2024, 12, 31),
            (2026, 9, 8),
            (2100, 3, 1),
        ],
    )
    def test_the_day_count_matches_the_host(self, year, month, day):
        # the host's calendar is an independent implementation of the same rules
        expected = (datetime.date(year, month, day) - datetime.date(1, 1, 1)).days
        assert to_days(year, month, day) == expected

    @pytest.mark.parametrize("offset", [0, 1, 365, 366, 100000, 700000])
    def test_going_back_from_a_count_matches_the_host(self, offset):
        expected = datetime.date(1, 1, 1) + datetime.timedelta(days=offset)
        assert from_days(offset) == (expected.year, expected.month, expected.day)

    @pytest.mark.parametrize(
        "year,month,day", [(2026, 9, 8), (2000, 1, 1), (1999, 12, 31), (2024, 2, 29)]
    )
    def test_the_weekday_matches_the_host(self, year, month, day):
        expected = datetime.date(year, month, day).isoweekday()
        assert to_days(year, month, day) % 7 + 1 == expected

    def test_a_round_trip_returns_the_same_date(self):
        for offset in range(0, 40000, 733):
            year, month, day = from_days(offset)
            assert to_days(year, month, day) == offset


class TestDates:
    def test_a_date_comes_back_as_three_numbers(self):
        assert evaluate("date(2026, 9, 8)") == "[2026, 9, 8]"

    def test_a_day_past_the_end_of_a_month_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print date(2023, 2, 29);")
        assert "only 28 days" in str(caught.value)

    def test_the_leap_day_is_allowed_in_a_leap_year(self):
        assert evaluate("date(2024, 2, 29)") == "[2024, 2, 29]"

    def test_a_year_before_one_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print date(0, 1, 1);")
        assert "before the calendar starts" in str(caught.value)

    def test_a_month_of_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print date(2020, 0, 1);")

    def test_a_date_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print date(2020.5, 1, 1);")

    def test_a_date_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print weekday(5);")
        assert "list of three numbers" in str(caught.value)

    def test_a_list_of_the_wrong_length_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print weekday([2020, 1]);")


class TestArithmetic:
    def test_the_days_between_two_dates(self):
        assert evaluate("daysBetween(date(2026, 1, 1), date(2026, 1, 31))") == "30"

    def test_the_days_between_a_date_and_itself_is_zero(self):
        assert evaluate("daysBetween(date(2026, 1, 1), date(2026, 1, 1))") == "0"

    def test_going_backwards_gives_a_negative_count(self):
        assert evaluate("daysBetween(date(2026, 1, 31), date(2026, 1, 1))") == "-30"

    def test_a_leap_year_is_three_hundred_and_sixty_six_days(self):
        assert evaluate("daysBetween(date(2024, 1, 1), date(2025, 1, 1))") == "366"

    def test_a_common_year_is_three_hundred_and_sixty_five(self):
        assert evaluate("daysBetween(date(2023, 1, 1), date(2024, 1, 1))") == "365"

    def test_adding_days_crosses_a_month(self):
        assert evaluate("addDays(date(2026, 1, 31), 1)") == "[2026, 2, 1]"

    def test_adding_days_crosses_a_year(self):
        assert evaluate("addDays(date(2026, 12, 31), 1)") == "[2027, 1, 1]"

    def test_subtracting_days_works_too(self):
        assert evaluate("addDays(date(2026, 3, 1), -1)") == "[2026, 2, 28]"

    def test_adding_zero_days_changes_nothing(self):
        assert evaluate("addDays(date(2026, 5, 5), 0)") == "[2026, 5, 5]"

    def test_moving_before_the_calendar_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print addDays(date(1, 1, 1), -1);")


class TestClamping:
    def test_a_month_added_to_the_end_of_january_clamps(self):
        # clamping is what people mean by the same day next month
        assert evaluate("addMonths(date(2023, 1, 31), 1)") == "[2023, 2, 28]"

    def test_it_clamps_to_the_leap_day_in_a_leap_year(self):
        assert evaluate("addMonths(date(2024, 1, 31), 1)") == "[2024, 2, 29]"

    def test_a_month_added_to_a_safe_day_does_not_clamp(self):
        assert evaluate("addMonths(date(2026, 1, 15), 1)") == "[2026, 2, 15]"

    def test_adding_a_month_twice_can_differ_from_adding_two(self):
        # the documented consequence of clamping
        once_twice = evaluate("addMonths(addMonths(date(2023, 1, 31), 1), 1)")
        at_once = evaluate("addMonths(date(2023, 1, 31), 2)")
        assert once_twice == "[2023, 3, 28]"
        assert at_once == "[2023, 3, 31]"
        assert once_twice != at_once

    def test_adding_twelve_months_is_a_year(self):
        assert evaluate("addMonths(date(2026, 5, 5), 12)") == "[2027, 5, 5]"

    def test_subtracting_months_crosses_a_year(self):
        assert evaluate("addMonths(date(2026, 1, 15), -1)") == "[2025, 12, 15]"

    def test_adding_a_year_to_a_leap_day_clamps(self):
        assert evaluate("addYears(date(2024, 2, 29), 1)") == "[2025, 2, 28]"

    def test_adding_four_years_to_a_leap_day_does_not(self):
        assert evaluate("addYears(date(2024, 2, 29), 4)") == "[2028, 2, 29]"

    def test_moving_years_before_the_calendar_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print addYears(date(1, 1, 1), -1);")


class TestNaming:
    def test_the_epoch_was_a_monday(self):
        assert evaluate("weekday(date(1, 1, 1))") == "1"

    def test_a_weekday_is_named(self):
        assert evaluate("weekdayName(date(2026, 9, 8))") == "Tuesday"

    def test_a_month_is_named(self):
        assert evaluate("monthName(date(2026, 9, 8))") == "September"

    def test_a_saturday_is_a_weekend(self):
        assert evaluate("isWeekend(date(2026, 9, 12))") == "true"

    def test_a_tuesday_is_not(self):
        assert evaluate("isWeekend(date(2026, 9, 8))") == "false"

    def test_the_day_of_the_year(self):
        assert evaluate("dayOfYear(date(2026, 1, 1))") == "1"

    def test_the_last_day_of_a_leap_year(self):
        assert evaluate("dayOfYear(date(2024, 12, 31))") == "366"

    def test_the_week_of_the_year(self):
        assert evaluate("weekOfYear(date(2026, 1, 1))") == "1"

    def test_the_eighth_day_starts_the_second_week(self):
        assert evaluate("weekOfYear(date(2026, 1, 8))") == "2"


class TestFormatting:
    def test_a_date_formats_with_padding(self):
        assert evaluate("formatDate(date(2026, 9, 8))") == "2026-09-08"

    def test_an_early_year_pads_to_four_digits(self):
        assert evaluate("formatDate(date(1, 1, 1))") == "0001-01-01"

    def test_a_long_form_names_the_day_and_month(self):
        assert evaluate("longDate(date(2026, 9, 8))") == "Tuesday 8 September 2026"

    def test_a_date_can_be_read_back(self):
        assert evaluate('parseDate("2026-09-08")') == "[2026, 9, 8]"

    def test_formatting_and_parsing_are_inverses(self):
        assert evaluate('parseDate(formatDate(date(2026, 9, 8)))') == "[2026, 9, 8]"

    def test_text_in_the_wrong_shape_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print parseDate("8 September 2026");')
        assert "year-month-day" in str(caught.value)

    def test_text_with_a_word_in_it_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output('print parseDate("2026-Sep-08");')

    def test_an_impossible_date_is_refused_on_reading(self):
        with pytest.raises(Arithmetic):
            run_output('print parseDate("2023-02-29");')

    def test_something_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print parseDate(20260908);")


class TestComparing:
    def test_an_earlier_date_is_before_a_later_one(self):
        assert evaluate("isBefore(date(2026, 1, 1), date(2026, 1, 2))") == "true"

    def test_a_later_date_is_not(self):
        assert evaluate("isBefore(date(2026, 1, 2), date(2026, 1, 1))") == "false"

    def test_a_date_is_not_before_itself(self):
        assert evaluate("isBefore(date(2026, 1, 1), date(2026, 1, 1))") == "false"

    def test_two_equal_dates_are_the_same(self):
        assert evaluate("sameDate(date(2026, 1, 1), date(2026, 1, 1))") == "true"

    def test_two_different_dates_are_not(self):
        assert evaluate("sameDate(date(2026, 1, 1), date(2026, 1, 2))") == "false"


class TestEaster:
    @pytest.mark.parametrize(
        "year,month,day",
        [
            (1900, 4, 15),
            (1999, 4, 4),
            (2000, 4, 23),
            (2020, 4, 12),
            (2021, 4, 4),
            (2022, 4, 17),
            (2023, 4, 9),
            (2024, 3, 31),
            (2025, 4, 20),
            (2026, 4, 5),
            (2027, 3, 28),
            (2030, 4, 21),
        ],
    )
    def test_it_matches_the_published_date(self, year, month, day):
        # the first version of this was wrong for every one of these, by one to five
        # days, which is why they are pinned rather than trusted
        assert _easter_of([year]) == [year, month, day]

    def test_easter_always_falls_in_march_or_april(self):
        for year in range(1900, 2100):
            assert _easter_of([year])[1] in (3, 4)

    def test_easter_always_falls_on_a_sunday(self):
        for year in range(1900, 2100):
            found = _easter_of([year])
            assert to_days(*found) % 7 + 1 == 7

    def test_a_program_can_ask(self):
        assert evaluate("easter(2026)") == "[2026, 4, 5]"

    def test_a_year_before_one_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print easter(0);")


class TestDayNumbers:
    def test_the_epoch_is_day_zero(self):
        assert evaluate("dayNumber(date(1, 1, 1))") == "0"

    def test_a_day_number_converts_back(self):
        assert evaluate("dateFromNumber(dayNumber(date(2026, 9, 8)))") == "[2026, 9, 8]"

    def test_a_negative_day_number_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print dateFromNumber(-1);")


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "date(2026, 9, 8)",
            "isLeapYear(2024)",
            "daysBetween(date(2020, 1, 1), date(2026, 9, 8))",
            "addDays(date(2026, 2, 28), 2)",
            "addMonths(date(2023, 1, 31), 1)",
            "addYears(date(2024, 2, 29), 1)",
            "weekdayName(date(2026, 9, 8))",
            "formatDate(date(2026, 9, 8))",
            "longDate(date(2026, 9, 8))",
            'parseDate("2026-09-08")',
            "easter(2026)",
            "dayOfYear(date(2026, 12, 31))",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
