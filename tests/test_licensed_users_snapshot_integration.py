# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Integration test for lambda/licensed_users_snapshot/index.py (task 18.2).

moto has no QuickSight mocking support (see tests/test_licensed_users_snapshot_lambda.py),
so `quicksight.list_users` is still patched manually via unittest.mock. What this test adds
beyond the task 3.3 property test is a *real* S3 backend: moto's `mock_aws` stands up an
in-memory S3 bucket, the Lambda's `put_object` call goes through moto's actual S3 API
implementation, and the test reads the object back out with a real `get_object` call to
verify the bytes that actually landed in S3 -- rather than only inspecting the arguments a
mock recorded. This is a fixed, 1-3 example integration check (no/single/multi-page
pagination), not a property test.

Note: the module-level `s3` client in lambda/licensed_users_snapshot/index.py is
constructed once at import time (before any mock is active), so it must be swapped for a
client built while `mock_aws()` is active -- otherwise boto3 tries to sign real requests
with no credentials. This is done with `patch.object(index, "s3", ...)`, same mechanism the
existing task 3.3 test already uses for `index.quicksight`.

**Validates: Requirements 5.1, 5.3**
"""
import importlib
import json
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

index = importlib.import_module("lambda.licensed_users_snapshot.index")

BUCKET = "test-licensed-users-bucket"
ACCOUNT_ID = "123456789012"


def _user(i):
    return {
        "UserName": f"user-{i}",
        "Arn": f"arn:aws:quicksight:us-east-1:123456789012:user/default/user-{i}",
        "Email": f"user{i}@example.com",
        "Role": "AUTHOR",
        "IdentityType": "QUICKSIGHT",
        "Active": True,
    }


def _paged_list_users_side_effect(pages):
    """Return `pages` in order, wiring up NextToken so the real pagination
    loop in list_all_users is exercised end-to-end."""
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


@pytest.mark.parametrize(
    "pages",
    [
        [[]],  # no users
        [[_user(0)]],  # single page, single user
        [[_user(0), _user(1)], [_user(2)]],  # multi-page pagination
    ],
    ids=["no-users", "single-page", "multi-page"],
)
@mock_aws
def test_snapshot_written_to_real_s3_round_trips(pages, monkeypatch):
    """
    Runs the Lambda's real pagination loop (list_all_users) against a mocked
    QuickSight client, then lets the resulting put_object call hit a real
    (moto-backed, in-memory) S3 bucket. Confirms the object that actually
    exists in S3 -- read back with a real get_object call -- contains one
    JSON-lines record per user with username/ARN/email/role populated.
    """
    monkeypatch.setenv("AWS_ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setenv("DATA_LAKE_BUCKET", BUCKET)
    monkeypatch.setenv("QUICKSIGHT_NAMESPACE", "default")

    # moto is active here, so this client is a mocked, in-memory S3 backend.
    s3_client = boto3.client("s3", region_name="us-east-1")
    s3_client.create_bucket(Bucket=BUCKET)

    expected_users = [u for page in pages for u in page]

    with patch.object(index, "s3", s3_client), patch.object(
        index.quicksight, "list_users", side_effect=_paged_list_users_side_effect(pages)
    ):
        result = index.lambda_handler({}, None)

    # Real S3 read-back, not a mock call-args inspection.
    obj = s3_client.get_object(Bucket=BUCKET, Key=result["key"])
    body = obj["Body"].read().decode("utf-8")
    lines = [line for line in body.split("\n") if line]

    assert len(lines) == len(expected_users)
    records = [json.loads(line) for line in lines]
    expected_by_username = {u["UserName"]: u for u in expected_users}

    for record in records:
        expected = expected_by_username[record["username"]]
        assert record["user_arn"] == expected["Arn"] and record["user_arn"]
        assert record["email"] == expected["Email"] and record["email"]
        assert record["role"] == expected["Role"] and record["role"]

    assert result["usersWritten"] == len(expected_users)

    # A second real listing confirms exactly one object was written for the day.
    listing = s3_client.list_objects_v2(Bucket=BUCKET, Prefix="licensed-users-snapshot/")
    assert listing.get("KeyCount", 0) == 1
