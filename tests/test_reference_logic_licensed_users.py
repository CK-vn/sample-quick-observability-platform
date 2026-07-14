# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Property tests for the licensed-user-inactivity reference-logic functions in
tests/reference_logic.py (last_activity_timestamp, inactivity_period,
filter_by_inactivity_threshold, project_inactive_users_table), per
tasks.md tasks 9.2, 9.4, 9.6, 9.8.
"""
from datetime import date, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.reference_logic import (
    filter_by_inactivity_threshold,
    inactivity_period,
    last_activity_timestamp,
    project_inactive_users_table,
)

TARGET_USER = "target-user"
OTHER_USER_NAMES = ["alice", "bob", "carol", "dave"]


def _timestamps(min_value=date(2023, 1, 1), max_value=date(2023, 6, 30)):
    return st.datetimes(
        min_value=datetime(min_value.year, min_value.month, min_value.day),
        max_value=datetime(max_value.year, max_value.month, max_value.day),
    )


def _records_for_user(user_names, max_size=10):
    """Generate a list of {"user_name": ..., "event_time": ...} records drawn
    from `user_names`, used to build one of the four activity sources."""
    return st.lists(
        st.fixed_dictionaries(
            {
                "user_name": st.sampled_from(user_names),
                "event_time": _timestamps(),
            }
        ),
        max_size=max_size,
    )


def _four_sources(user_names):
    """Generate the four per-source record lists (chat, agent_hours,
    index_usage, api_audit) used by last_activity_timestamp."""
    return st.tuples(
        _records_for_user(user_names),
        _records_for_user(user_names),
        _records_for_user(user_names),
        _records_for_user(user_names),
    )


# ---------------------------------------------------------------------------
# Task 9.2 - Property 9: Last activity timestamp is the maximum of available
# per-source timestamps, or null
# Validates: Requirements 6.2, 6.3
# ---------------------------------------------------------------------------
@given(sources=_four_sources(OTHER_USER_NAMES + [TARGET_USER]))
@settings(max_examples=100, deadline=None)
def test_last_activity_timestamp_is_max_across_sources(sources):
    """**Validates: Requirements 6.2, 6.3**

    last_activity_timestamp returns the max event_time among the target
    user's records across all four sources (chat, agent_hours, index_usage,
    api_audit), regardless of which source(s) they appear in, ignoring
    noise records belonging to other users.
    """
    chat, agent_hours, index_usage, api_audit = sources

    result = last_activity_timestamp(TARGET_USER, chat, agent_hours, index_usage, api_audit)

    expected_timestamps = [
        record["event_time"]
        for source in (chat, agent_hours, index_usage, api_audit)
        for record in source
        if record["user_name"] == TARGET_USER
    ]

    if expected_timestamps:
        assert result == max(expected_timestamps)
    else:
        assert result is None


@given(sources=_four_sources(OTHER_USER_NAMES))
@settings(max_examples=100, deadline=None)
def test_last_activity_timestamp_is_none_when_user_absent_from_all_sources(sources):
    """**Validates: Requirements 6.2, 6.3**

    When the target user has zero matching records in any of the four
    sources (only noise records for other users are present),
    last_activity_timestamp returns None.
    """
    chat, agent_hours, index_usage, api_audit = sources

    result = last_activity_timestamp(TARGET_USER, chat, agent_hours, index_usage, api_audit)

    assert result is None


# ---------------------------------------------------------------------------
# Task 9.4 - Property 10: Inactivity period falls back to the creation-date
# proxy when there is no activity
# Validates: Requirements 6.7
# ---------------------------------------------------------------------------
def _first_seen_and_now():
    """Generate (first_seen_date, now) pairs with first_seen_date <= now, so
    the resulting day-diff is non-negative (mirrors a real "account created,
    then observed later" ordering)."""
    return st.tuples(_dates_only(), st.integers(min_value=0, max_value=730)).map(
        lambda t: (t[0], t[0] + timedelta(days=t[1]))
    )


def _dates_only(min_value=date(2020, 1, 1), max_value=date(2024, 12, 31)):
    return st.dates(min_value=min_value, max_value=max_value)


@given(first_seen_now=_first_seen_and_now())
@settings(max_examples=100, deadline=None)
def test_inactivity_period_falls_back_to_first_seen_date_when_no_activity(first_seen_now):
    """**Validates: Requirements 6.7**

    When last_activity_timestamp is None, inactivity_period falls back to
    the creation-date proxy: (now - first_seen_date).days.
    """
    first_seen_date, now = first_seen_now

    result = inactivity_period(None, first_seen_date, now)

    assert result == (now - first_seen_date).days


@given(
    last_activity=_timestamps(min_value=date(2020, 1, 1), max_value=date(2023, 12, 31)),
    first_seen_date=_dates_only(),
    now=_dates_only(min_value=date(2023, 1, 1), max_value=date(2024, 12, 31)),
)
@settings(max_examples=100, deadline=None)
def test_inactivity_period_uses_last_activity_and_ignores_first_seen_date_when_present(
    last_activity, first_seen_date, now
):
    """**Validates: Requirements 6.7**

    When last_activity_timestamp is not None, inactivity_period uses it
    (as a date) as the reference point and disregards first_seen_date
    entirely -- changing first_seen_date must not change the result.
    """
    result = inactivity_period(last_activity, first_seen_date, now)

    assert result == (now - last_activity.date()).days

    # Changing first_seen_date should have no effect when activity exists.
    other_first_seen_date = first_seen_date + timedelta(days=1)
    result_with_other_first_seen = inactivity_period(last_activity, other_first_seen_date, now)
    assert result_with_other_first_seen == result


# ---------------------------------------------------------------------------
# Task 9.6 - Property 11: Inactivity threshold filter selects
# greater-or-equal users
# Validates: Requirements 6.6
# ---------------------------------------------------------------------------
def _users_with_inactivity_period(max_size=30):
    return st.lists(
        st.fixed_dictionaries(
            {
                "user_name": st.text(min_size=1, max_size=10),
                "inactivity_period": st.integers(min_value=0, max_value=1000),
            }
        ),
        max_size=max_size,
    )


@given(
    users=_users_with_inactivity_period(),
    threshold_days=st.integers(min_value=0, max_value=1000),
)
@settings(max_examples=100, deadline=None)
def test_filter_by_inactivity_threshold_selects_greater_or_equal_users(users, threshold_days):
    """**Validates: Requirements 6.6**

    filter_by_inactivity_threshold returns exactly the users whose
    inactivity_period is greater than or equal to threshold_days --
    including users whose inactivity_period equals the threshold.
    """
    result = filter_by_inactivity_threshold(users, threshold_days)

    expected = [u for u in users if u["inactivity_period"] >= threshold_days]
    assert result == expected

    for user in result:
        assert user["inactivity_period"] >= threshold_days
    for user in users:
        if user["inactivity_period"] < threshold_days:
            assert user not in result


def test_filter_by_inactivity_threshold_includes_boundary_equal_user():
    """**Validates: Requirements 6.6**

    A user whose inactivity_period exactly equals threshold_days is
    included (greater-than-or-equal, not strict greater-than).
    """
    users = [
        {"user_name": "equal-to-threshold", "inactivity_period": 30},
        {"user_name": "above-threshold", "inactivity_period": 31},
        {"user_name": "below-threshold", "inactivity_period": 29},
    ]

    result = filter_by_inactivity_threshold(users, 30)

    result_names = {u["user_name"] for u in result}
    assert result_names == {"equal-to-threshold", "above-threshold"}


# ---------------------------------------------------------------------------
# Task 9.8 - Property 12: Inactive users table always includes required
# display fields
# Validates: Requirements 6.8
# ---------------------------------------------------------------------------
REQUIRED_TABLE_FIELDS = {"user_name", "role", "last_activity_timestamp", "inactivity_period"}


def _users_with_extra_keys(max_size=30):
    return st.lists(
        st.fixed_dictionaries(
            {
                "user_name": st.text(min_size=1, max_size=10),
                "role": st.sampled_from(["ADMIN", "AUTHOR", "READER"]),
                "last_activity_timestamp": st.one_of(st.none(), _timestamps()),
                "inactivity_period": st.integers(min_value=0, max_value=1000),
                # Extra unrelated keys that must be dropped by the projection.
                "email": st.text(max_size=10),
                "account_id": st.integers(),
            }
        ),
        max_size=max_size,
    )


@given(users=_users_with_extra_keys())
@settings(max_examples=100, deadline=None)
def test_project_inactive_users_table_includes_exactly_required_fields(users):
    """**Validates: Requirements 6.8**

    project_inactive_users_table output rows contain exactly the four
    required display fields (user_name, role, last_activity_timestamp,
    inactivity_period) -- no extra keys -- with values matching the input,
    for every input row.
    """
    result = project_inactive_users_table(users)

    assert len(result) == len(users)

    for input_user, output_row in zip(users, result):
        assert set(output_row.keys()) == REQUIRED_TABLE_FIELDS
        assert output_row["user_name"] == input_user["user_name"]
        assert output_row["role"] == input_user["role"]
        assert output_row["last_activity_timestamp"] == input_user["last_activity_timestamp"]
        assert output_row["inactivity_period"] == input_user["inactivity_period"]
