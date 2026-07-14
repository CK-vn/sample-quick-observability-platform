# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Property and unit tests for the usage/adoption reference-logic functions in
tests/reference_logic.py (daily_active_users, filter_by_date_range,
aggregate, usage_volume_total_and_average, agent_hours_total_and_average,
function_usage_distribution), per tasks.md tasks 7.2, 7.4, 7.6, 7.8, 7.10,
7.11, 7.12.
"""
from datetime import date, timedelta

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.reference_logic import (
    aggregate,
    agent_hours_total_and_average,
    daily_active_users,
    filter_by_date_range,
    function_usage_distribution,
    usage_volume_total_and_average,
)

USER_NAMES = ["alice", "bob", "carol", "dave", "eve", "frank"]

CHAT_INCLUDED_FEATURES = ["System Chat Agent", "System Chat Agent v2", "Custom Chat Agent", "Flow"]
AGENT_HOURS_INCLUDED_TYPES = ["Research", "Flow", "Automation"]
AGENT_HOURS_EXCLUDED_TYPES = ["Chat", "Unknown", ""]


def _dates(min_value=date(2023, 1, 1), max_value=date(2023, 3, 31)):
    return st.dates(min_value=min_value, max_value=max_value)


def _date_range():
    """Generate a (start, end) pair with start <= end and a bounded span, so
    per-day enumeration in daily_active_users stays fast."""
    return st.tuples(_dates(), st.integers(min_value=0, max_value=20)).map(
        lambda t: (t[0], t[0] + timedelta(days=t[1]))
    )


def _records_with_event_time(min_value=date(2022, 12, 20), max_value=date(2023, 4, 10)):
    return st.lists(
        st.fixed_dictionaries(
            {
                "user_name": st.sampled_from(USER_NAMES),
                "event_time": _dates(min_value=min_value, max_value=max_value),
            }
        ),
        max_size=60,
    )


# ---------------------------------------------------------------------------
# Task 7.2 - Property 1: Daily active user series is complete and correct
# Validates: Requirements 1.1, 1.4
# ---------------------------------------------------------------------------
@given(records=_records_with_event_time(), date_range=_date_range())
@settings(max_examples=100, deadline=None)
def test_daily_active_users_series_is_complete_and_correct(records, date_range):
    """**Validates: Requirements 1.1, 1.4**

    daily_active_users produces exactly one entry per calendar day in
    [start, end], each value equal to the distinct user_name count for that
    day, and 0 for days with no matching records.
    """
    start, end = date_range

    result = daily_active_users(records, start, end)

    expected_days = []
    day = start
    while day <= end:
        expected_days.append(day)
        day += timedelta(days=1)
    assert list(result.keys()) == expected_days

    for day in expected_days:
        expected_users = {r["user_name"] for r in records if r["event_time"] == day}
        assert result[day] == len(expected_users)
        if not expected_users:
            assert result[day] == 0


# ---------------------------------------------------------------------------
# Task 7.4 - Property 2: Date-range filtering commutes with aggregation
# Validates: Requirements 1.2, 2.3, 3.3, 4.5
# ---------------------------------------------------------------------------
def _distinct_user_count(records):
    return len({r["user_name"] for r in records})


def _total_record_count(records):
    return len(records)


@given(
    records=_records_with_event_time(),
    date_range=_date_range(),
    agg_name=st.sampled_from(["distinct_user_count", "total_record_count"]),
)
@settings(max_examples=100, deadline=None)
def test_date_range_filtering_commutes_with_aggregation(records, date_range, agg_name):
    """**Validates: Requirements 1.2, 2.3, 3.3, 4.5**

    Aggregating over filter_by_date_range(records, start, end) equals
    aggregating directly over an independently pre-filtered subset, for both
    a distinct-count and a total-count aggregate.
    """
    start, end = date_range
    agg_fn = _distinct_user_count if agg_name == "distinct_user_count" else _total_record_count

    filtered_then_aggregated = aggregate(filter_by_date_range(records, start, end), agg_fn)

    independently_filtered = [r for r in records if start <= r["event_time"] <= end]
    aggregated_independently = aggregate(independently_filtered, agg_fn)

    assert filtered_then_aggregated == aggregated_independently


# ---------------------------------------------------------------------------
# Task 7.6 - Property 3: Usage volume total and average are internally consistent
# Validates: Requirements 2.1, 2.2
# ---------------------------------------------------------------------------
@given(records=_records_with_event_time())
@settings(max_examples=100, deadline=None)
def test_usage_volume_total_and_average_internally_consistent(records):
    """**Validates: Requirements 2.1, 2.2**

    average == total / distinct_day_count, or average == 0 when there are no
    records (no distinct days to divide by).
    """
    result = usage_volume_total_and_average(records)

    assert result.total == len(records)

    distinct_days = len({r["event_time"] for r in records})
    if distinct_days == 0:
        assert result.average == 0
    else:
        assert result.average == pytest.approx(result.total / distinct_days)


# ---------------------------------------------------------------------------
# Task 7.8 - Property 4: Agent Hours volume total and average are internally consistent
# Validates: Requirements 3.1, 3.2
# ---------------------------------------------------------------------------
def _agent_hours_records():
    return st.lists(
        st.fixed_dictionaries(
            {
                "event_time": _dates(),
                "hours": st.floats(
                    min_value=0, max_value=1000, allow_nan=False, allow_infinity=False
                ),
            }
        ),
        max_size=60,
    )


@given(records=_agent_hours_records())
@settings(max_examples=100, deadline=None)
def test_agent_hours_total_and_average_internally_consistent(records):
    """**Validates: Requirements 3.1, 3.2**

    average == sum(hours) / distinct_day_count, or average == 0 when there
    are no records.
    """
    result = agent_hours_total_and_average(records)

    expected_total = sum(r["hours"] for r in records)
    assert result.total == pytest.approx(expected_total)

    distinct_days = len({r["event_time"] for r in records})
    if distinct_days == 0:
        assert result.average == 0
    else:
        assert result.average == pytest.approx(expected_total / distinct_days)


# ---------------------------------------------------------------------------
# Tasks 7.10 / 7.11 / 7.12 shared strategies for function_usage_distribution
# ---------------------------------------------------------------------------
def _chat_records(features=CHAT_INCLUDED_FEATURES, max_size=40):
    return st.lists(
        st.fixed_dictionaries({"feature": st.sampled_from(features)}), max_size=max_size
    )


def _agent_hours_usage_records(resource_types=AGENT_HOURS_INCLUDED_TYPES, max_size=40):
    return st.lists(
        st.fixed_dictionaries({"resource_type": st.sampled_from(resource_types)}),
        max_size=max_size,
    )


# ---------------------------------------------------------------------------
# Task 7.10 - Property 5: Function usage percentages equal each category's
# share and sum to 100%
# Validates: Requirements 4.1, 4.4
# ---------------------------------------------------------------------------
@given(chat_records=_chat_records(), agent_hours_records=_agent_hours_usage_records())
@settings(max_examples=100, deadline=None)
def test_function_usage_percentages_match_share_and_sum_to_100(chat_records, agent_hours_records):
    """**Validates: Requirements 4.1, 4.4**

    For randomized non-empty chat/agent-hours records restricted to the
    included categories, each category's percentage equals its count / total
    * 100, and all percentages sum to 100 within floating-point tolerance.
    """
    assume(len(chat_records) + len(agent_hours_records) > 0)

    result = function_usage_distribution(chat_records, agent_hours_records)

    counts = {}
    for record in chat_records:
        feature = record["feature"]
        category = "System Chat Agent" if feature.startswith("System Chat Agent") else feature
        counts[category] = counts.get(category, 0) + 1
    for record in agent_hours_records:
        resource_type = record["resource_type"]
        counts[resource_type] = counts.get(resource_type, 0) + 1

    total = sum(counts.values())
    assert set(result.keys()) == set(counts.keys())
    for category, count in counts.items():
        assert result[category] == pytest.approx(count / total * 100)

    assert sum(result.values()) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Task 7.11 - Property 6: Chat and Agent Hours "Flow" usage combine into one
# category
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------
@given(
    n_chat_flow=st.integers(min_value=0, max_value=20),
    n_agent_flow=st.integers(min_value=0, max_value=20),
    other_chat_records=_chat_records(features=["Custom Chat Agent", "System Chat Agent"]),
    other_agent_records=_agent_hours_usage_records(resource_types=["Research", "Automation"]),
)
@settings(max_examples=100, deadline=None)
def test_chat_and_agent_hours_flow_combine_into_one_category(
    n_chat_flow, n_agent_flow, other_chat_records, other_agent_records
):
    """**Validates: Requirements 4.3**

    Chat records with feature="Flow" and Agent Hours records with
    resource_type="Flow" are reported as a single "Flow" key whose
    underlying count equals the sum of both sources' Flow counts, not two
    separate entries.
    """
    chat_records = other_chat_records + [{"feature": "Flow"}] * n_chat_flow
    agent_hours_records = other_agent_records + [{"resource_type": "Flow"}] * n_agent_flow

    result = function_usage_distribution(chat_records, agent_hours_records)

    flow_total_records = n_chat_flow + n_agent_flow
    total_included = len(chat_records) + len(agent_hours_records)

    if flow_total_records == 0:
        assert "Flow" not in result
        return

    assert list(result).count("Flow") == 1
    reconstructed_flow_count = result["Flow"] * total_included / 100
    assert reconstructed_flow_count == pytest.approx(flow_total_records)


# ---------------------------------------------------------------------------
# Task 7.12 - unit test for the static function-category inclusion list
# Requirements: 4.2
# ---------------------------------------------------------------------------
def test_function_usage_distribution_excludes_unrecognized_categories():
    """Requirements: 4.2 - function_usage_distribution excludes any category
    not in {System Chat Agent, Custom Chat Agent, Flow, Research, Automation}."""
    chat_records = [
        {"feature": "Unrecognized Feature"},
        {"feature": ""},
        {"feature": "Flow"},
    ]
    agent_hours_records = [
        {"resource_type": "Chat"},
        {"resource_type": "Research"},
    ]

    result = function_usage_distribution(chat_records, agent_hours_records)

    assert "Unrecognized Feature" not in result
    assert "" not in result
    assert "Chat" not in result
    assert set(result.keys()) == {"Flow", "Research"}
    assert result["Flow"] == pytest.approx(50.0)
    assert result["Research"] == pytest.approx(50.0)


def test_function_usage_distribution_returns_empty_dict_for_only_excluded_categories():
    """Requirements: 4.2 - when no records fall in the included categories,
    the result is empty rather than including excluded categories."""
    chat_records = [{"feature": "Unrecognized"}, {"feature": ""}]
    agent_hours_records = [{"resource_type": "Chat"}, {"resource_type": "Unknown"}]

    result = function_usage_distribution(chat_records, agent_hours_records)

    assert result == {}
