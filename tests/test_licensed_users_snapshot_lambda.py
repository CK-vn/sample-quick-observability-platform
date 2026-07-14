# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Tests for lambda/licensed_users_snapshot/index.py (Licensed_Users_Snapshot_Lambda)

moto has no QuickSight mocking support, so the module-level `quicksight` and
`s3` boto3 clients are patched directly via unittest.mock rather than moto.
"""
import importlib
import json
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

index = importlib.import_module("lambda.licensed_users_snapshot.index")

ROLES = ["ADMIN", "AUTHOR", "READER", "RESTRICTED_READER", "RESTRICTED_AUTHOR"]
IDENTITY_TYPES = ["IAM", "QUICKSIGHT"]

EXCEPTION_TYPES = [RuntimeError, ValueError, ConnectionError, TimeoutError, Exception]


@st.composite
def users_and_pages(draw):
    """
    Generate a random list of QuickSight-shaped user dicts (0..12 users) plus
    a pagination of that list into 1..N pages, exercising the 0/1/multi-page
    cases required by task 3.3.
    """
    n = draw(st.integers(min_value=0, max_value=12))
    users = []
    for i in range(n):
        users.append(
            {
                "UserName": f"user-{i}",
                "Arn": f"arn:aws:quicksight:us-east-1:123456789012:user/default/user-{i}",
                "Email": f"user{i}@example.com",
                "Role": draw(st.sampled_from(ROLES)),
                "IdentityType": draw(st.sampled_from(IDENTITY_TYPES)),
                "Active": draw(st.booleans()),
            }
        )

    page_size = draw(st.integers(min_value=1, max_value=max(n, 1)))
    if n == 0:
        pages = [[]]
    else:
        pages = [users[i : i + page_size] for i in range(0, n, page_size)]

    return users, pages


def _paged_list_users_side_effect(pages):
    """Build a list_users side_effect that returns `pages` in order, wiring
    up NextToken so list_all_users' pagination loop is genuinely exercised."""
    state = {"i": 0}

    def side_effect(**kwargs):
        i = state["i"]
        page = pages[i]
        state["i"] += 1
        resp = {"UserList": page}
        if state["i"] < len(pages):
            resp["NextToken"] = f"token-{state['i']}"
        return resp

    return side_effect


ENV_VARS = {
    "AWS_ACCOUNT_ID": "123456789012",
    "DATA_LAKE_BUCKET": "test-bucket",
    "QUICKSIGHT_NAMESPACE": "default",
}


# ---------------------------------------------------------------------------
# Task 3.3 - Property 7: snapshot preserves all required fields for every user
# Validates: Requirements 5.1, 5.3
# ---------------------------------------------------------------------------
@given(data=users_and_pages())
@settings(max_examples=100, deadline=None)
def test_snapshot_preserves_all_required_fields_for_every_user(data):
    """**Validates: Requirements 5.1, 5.3**

    For 0, 1, and multi-page list_users results, exactly one put_object call
    is made whose body has one record per returned user with
    username/ARN/email/role populated.
    """
    users, pages = data

    with patch.dict(os.environ, ENV_VARS), patch.object(
        index.quicksight, "list_users", side_effect=_paged_list_users_side_effect(pages)
    ), patch.object(index.s3, "put_object") as mock_put_object:
        result = index.lambda_handler({}, None)

    assert mock_put_object.call_count == 1
    _, kwargs = mock_put_object.call_args
    body = kwargs["Body"].decode("utf-8")
    lines = [line for line in body.split("\n") if line]
    assert len(lines) == len(users)

    records = [json.loads(line) for line in lines]
    expected_by_username = {u["UserName"]: u for u in users}
    seen_usernames = set()
    for record in records:
        expected = expected_by_username[record["username"]]
        seen_usernames.add(record["username"])
        assert record["username"]
        assert record["user_arn"] == expected["Arn"] and record["user_arn"]
        assert record["email"] == expected["Email"] and record["email"]
        assert record["role"] == expected["Role"] and record["role"]

    assert seen_usernames == set(expected_by_username.keys())
    assert result["usersWritten"] == len(users)


# ---------------------------------------------------------------------------
# Task 3.4 - Property 8: a failed ListUsers call never produces a snapshot write
# Validates: Requirements 5.4
# ---------------------------------------------------------------------------
@given(
    exc_type=st.sampled_from(EXCEPTION_TYPES),
    message=st.text(min_size=1, max_size=50),
)
@settings(max_examples=50, deadline=None)
def test_failed_list_users_never_produces_snapshot_write(exc_type, message):
    """**Validates: Requirements 5.4**

    For randomized exception types/messages raised from list_users, the error
    is logged and put_object is never called.
    """
    with patch.dict(os.environ, ENV_VARS), patch.object(
        index.quicksight, "list_users", side_effect=exc_type(message)
    ), patch.object(index.s3, "put_object") as mock_put_object, patch(
        "builtins.print"
    ) as mock_print:
        with pytest.raises(exc_type):
            index.lambda_handler({}, None)

    mock_put_object.assert_not_called()
    logged_messages = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
    assert "Error calling QuickSight ListUsers" in logged_messages
    assert message in logged_messages


# ---------------------------------------------------------------------------
# Task 3.5 - unit test for the S3 key/prefix format
# Requirements: 5.1
# ---------------------------------------------------------------------------
def test_build_snapshot_key_format_for_fixed_date():
    """Requirements: 5.1 - build_snapshot_key matches the daily-partitioned
    licensed-users-snapshot/year=Y/month=MM/day=DD/snapshot.json format."""
    frozen_now = datetime(2024, 3, 7, 6, 0, 0, tzinfo=timezone.utc)

    key = index.build_snapshot_key(frozen_now)

    assert key == "licensed-users-snapshot/year=2024/month=03/day=07/snapshot.json"


def test_lambda_handler_writes_to_key_matching_frozen_date():
    """Requirements: 5.1 - the full handler writes to the S3 key derived from
    the current date, using a frozen `datetime.now` to pin the date."""
    frozen_now = datetime(2024, 3, 7, 6, 0, 0, tzinfo=timezone.utc)
    expected_key = "licensed-users-snapshot/year=2024/month=03/day=07/snapshot.json"

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now

    with patch.dict(os.environ, ENV_VARS), patch.object(
        index.quicksight, "list_users", return_value={"UserList": []}
    ), patch.object(index.s3, "put_object") as mock_put_object, patch.object(
        index, "datetime", FrozenDatetime
    ):
        result = index.lambda_handler({}, None)

    assert result["key"] == expected_key
    _, kwargs = mock_put_object.call_args
    assert kwargs["Key"] == expected_key
