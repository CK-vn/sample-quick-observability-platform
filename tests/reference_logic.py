# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Pure-Python reference re-implementations of the Athena view logic defined in
sql/*.sql (chat_activity, agent_hours_usage, function_usage_distribution,
licensed_users_activity).

Athena views cannot be executed inside a unit-test process (they require a
live Athena/Glue catalog), so this module mirrors the relevant SQL logic in
plain Python. Property tests (see design.md's "Testing Strategy" section)
exercise these functions directly to validate Properties 1-6 and 9-12
without needing AWS infrastructure. The actual SQL is exercised separately
by the integration tests in a later task (see tasks.md, task 18.3).

This module is test-only support code and is not imported by application
(Lambda/CDK) code.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

# Categories included from chat_activity's `feature` column (post-normalization,
# see _normalize_chat_feature) per sql/create_function_usage_distribution_view.sql.
_CHAT_INCLUDED_CATEGORIES = {"Flow", "Custom Chat Agent", "System Chat Agent"}

# Categories included from agent_hours_usage's `resource_type` column per
# sql/create_function_usage_distribution_view.sql. Note "Chat" is deliberately
# excluded to avoid double-counting chat usage already captured above.
_AGENT_HOURS_INCLUDED_CATEGORIES = {"Research", "Flow", "Automation"}


def _event_date(record: Dict[str, Any]) -> date:
    """Extract the calendar date from a record's `event_time` (datetime or date)."""
    event_time = record["event_time"]
    if isinstance(event_time, datetime):
        return event_time.date()
    return event_time


def daily_active_users(
    records: Sequence[Dict[str, Any]], start: date, end: date
) -> Dict[date, int]:
    """
    Mirrors the day-granularity DISTINCT_COUNT(user_name) grouping used by the
    "Daily Active Users" visual (backed by chat_activity, per design.md's
    `adopt-trend` retitle).

    Returns one entry per calendar day in [start, end] (inclusive), mapping
    that day to the number of distinct `user_name` values among records whose
    `event_time` falls on that day. Days with no matching records are
    zero-filled (Requirement 1.4) rather than omitted.
    """
    users_by_day: Dict[date, set] = {}
    for record in records:
        day = _event_date(record)
        if start <= day <= end:
            users_by_day.setdefault(day, set()).add(record["user_name"])

    result: Dict[date, int] = {}
    day = start
    while day <= end:
        result[day] = len(users_by_day.get(day, set()))
        day = date.fromordinal(day.toordinal() + 1)
    return result


def filter_by_date_range(
    records: Sequence[Dict[str, Any]], start: date, end: date
) -> List[Dict[str, Any]]:
    """
    Returns only the records whose `event_time` falls within [start, end]
    (inclusive of both endpoints), mirroring the `TimeRangeFilter` applied by
    the dashboard's date-range filter groups.
    """
    return [record for record in records if start <= _event_date(record) <= end]


def aggregate(
    records: Sequence[Dict[str, Any]], agg_fn: Callable[[Sequence[Dict[str, Any]]], Any]
) -> Any:
    """
    Generic thin wrapper that applies `agg_fn` to a record list. Exists so
    property tests can express "filtering then aggregating" and "aggregating
    the pre-filtered set" using the same composable building block (see
    Property 2: date-range filtering commutes with aggregation).
    """
    return agg_fn(records)


@dataclass(frozen=True)
class TotalAndAverage:
    """Result shape shared by usage_volume_total_and_average and
    agent_hours_total_and_average: a total measure and its daily average."""

    total: float
    average: float


def _distinct_day_count(records: Sequence[Dict[str, Any]]) -> int:
    return len({_event_date(record) for record in records})


def usage_volume_total_and_average(
    records: Sequence[Dict[str, Any]],
) -> TotalAndAverage:
    """
    Mirrors the Chat Activity "Usage Volume by Day" visuals: `total` is the
    total record count, and `average` is that total divided by the number of
    distinct calendar days present among the records (i.e. the count-per-day
    average), matching the `daily_avg_usage_volume` CalculatedField
    (`distinct_count({conversation_id}) / distinct_count(truncDate('DD', {event_time}))`).

    `average` is 0 when there are no records (no distinct days to divide by).
    """
    total = len(records)
    distinct_days = _distinct_day_count(records)
    average = total / distinct_days if distinct_days else 0
    return TotalAndAverage(total=total, average=average)


def agent_hours_total_and_average(
    records: Sequence[Dict[str, Any]],
) -> TotalAndAverage:
    """
    Mirrors the Agent Hours Usage "Volume by Day" visuals: `total` is the sum
    of the `hours` measure across all records, and `average` is that total
    divided by the number of distinct calendar days present, matching the
    `daily_avg_agent_hours` CalculatedField
    (`sum({hours}) / distinct_count(truncDate('DD', {event_time}))`).

    `average` is 0 when there are no records (no distinct days to divide by).
    """
    total = sum(record["hours"] for record in records)
    distinct_days = _distinct_day_count(records)
    average = total / distinct_days if distinct_days else 0
    return TotalAndAverage(total=total, average=average)


def _normalize_chat_feature(feature: str) -> Optional[str]:
    """
    Mirrors the CASE statement in sql/create_function_usage_distribution_view.sql:
    any `feature` matching 'System Chat Agent%' normalizes to "System Chat Agent";
    other included features pass through unchanged. Returns None if the feature
    is not one of the chat_activity categories included in the view's WHERE clause.
    """
    if feature.startswith("System Chat Agent"):
        return "System Chat Agent"
    if feature in ("Flow", "Custom Chat Agent"):
        return feature
    return None


def function_usage_distribution(
    chat_records: Sequence[Dict[str, Any]],
    agent_hours_records: Sequence[Dict[str, Any]],
) -> Dict[str, float]:
    """
    Mirrors sql/create_function_usage_distribution_view.sql's UNION ALL of:
      - chat_activity, restricted to feature IN ('Flow', 'Custom Chat Agent')
        OR feature LIKE 'System Chat Agent%' (normalized to "System Chat Agent")
      - agent_hours_usage, restricted to resource_type IN ('Research', 'Flow',
        'Automation') -- Agent Hours' "Chat" resource_type is excluded.

    Both sources' "Flow" rows merge into a single "Flow" category (Property 6).

    Returns a dict mapping each included category to its percentage share
    (record count for that category / total included record count * 100).
    Percentages sum to 100 (within floating-point tolerance) for any
    non-empty input. Returns an empty dict if there are no included records.
    """
    counts: Dict[str, int] = {}

    for record in chat_records:
        category = _normalize_chat_feature(record["feature"])
        if category is not None:
            counts[category] = counts.get(category, 0) + 1

    for record in agent_hours_records:
        resource_type = record["resource_type"]
        if resource_type in _AGENT_HOURS_INCLUDED_CATEGORIES:
            counts[resource_type] = counts.get(resource_type, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return {}

    return {category: count / total * 100 for category, count in counts.items()}


def last_activity_timestamp(
    user: str,
    chat: Sequence[Dict[str, Any]],
    agent_hours: Sequence[Dict[str, Any]],
    index_usage: Sequence[Dict[str, Any]],
    api_audit: Sequence[Dict[str, Any]],
) -> Optional[datetime]:
    """
    Mirrors sql/create_licensed_users_activity_view.sql's `activity` CTE (a
    4-way UNION ALL of chat_activity, agent_hours_usage, index_usage, and
    api_audit_trail) followed by `MAX(event_time) GROUP BY user_name`,
    restricted to a single `user`.

    Returns the maximum `event_time` among records in any of the four
    sources whose `user_name` equals `user`, or `None` if `user` has no
    matching records in any source (Requirement 6.2, 6.3).
    """
    timestamps = [
        record["event_time"]
        for source in (chat, agent_hours, index_usage, api_audit)
        for record in source
        if record["user_name"] == user
    ]
    return max(timestamps) if timestamps else None


def _to_date(value: Union[date, datetime]) -> date:
    """Normalize a date/datetime value to a plain `date` (see `_event_date`)."""
    if isinstance(value, datetime):
        return value.date()
    return value


def inactivity_period(
    last_activity_timestamp: Optional[datetime],
    first_seen_date: date,
    now: Union[date, datetime],
) -> int:
    """
    Mirrors sql/create_licensed_users_activity_view.sql's
    `date_diff('day', COALESCE(last_activity_timestamp, first_seen_date),
    CURRENT_TIMESTAMP)`: when `last_activity_timestamp` is `None` (the user
    has no activity in any of the four sources), falls back to the
    creation-date proxy `first_seen_date` (Requirement 6.7); otherwise uses
    `last_activity_timestamp`.

    Returns the number of calendar days between that reference point and
    `now`.
    """
    reference = last_activity_timestamp if last_activity_timestamp is not None else first_seen_date
    return (_to_date(now) - _to_date(reference)).days


def filter_by_inactivity_threshold(
    users: Sequence[Dict[str, Any]], threshold_days: float
) -> List[Dict[str, Any]]:
    """
    Mirrors the Licensed Users sheet's `NumericRangeFilter` on
    `inactivity_period` (`RangeMinimumValue={"Parameter":
    "InactivityThresholdDays"}`, `IncludeMinimum=True`): returns only the
    users whose `inactivity_period` is greater than or equal to
    `threshold_days` (Requirement 6.6).
    """
    return [user for user in users if user["inactivity_period"] >= threshold_days]


def project_inactive_users_table(users: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mirrors the `licensed-inactive-table` TABLE visual's projected columns
    (`user_name`, `role`, `last_activity_timestamp`, `inactivity_period`):
    returns one dict per input user containing exactly those four keys,
    dropping any other keys present on the input (Requirement 6.8).
    """
    return [
        {
            "user_name": user["user_name"],
            "role": user["role"],
            "last_activity_timestamp": user["last_activity_timestamp"],
            "inactivity_period": user["inactivity_period"],
        }
        for user in users
    ]
