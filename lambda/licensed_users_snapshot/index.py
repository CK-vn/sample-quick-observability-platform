# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Lambda function to snapshot QuickSight licensed users to S3
Paginates quicksight.list_users and writes one newline-delimited JSON
object per user to a daily-partitioned S3 key for Athena queries
"""
import json
import os
import traceback
from datetime import datetime, timezone

import boto3

quicksight = boto3.client("quicksight")
s3 = boto3.client("s3")


def lambda_handler(event, context):
    """
    Snapshot the current list of QuickSight licensed users to S3

    Input: EventBridge scheduled event (no meaningful payload)
    Output: Dict with the number of users written and the S3 key used
    """
    account_id = os.environ["AWS_ACCOUNT_ID"]
    bucket = os.environ["DATA_LAKE_BUCKET"]
    namespace = os.environ.get("QUICKSIGHT_NAMESPACE", "default")

    users = list_all_users(account_id, namespace)

    records = [transform_user(u, account_id) for u in users]

    now = datetime.now(timezone.utc)
    key = build_snapshot_key(now)

    # Write the full snapshot in one PutObject call - no partial writes.
    body = "\n".join(json.dumps(r) for r in records) + ("\n" if records else "")
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))

    return {"usersWritten": len(records), "key": key}


def list_all_users(account_id, namespace):
    """
    Paginate quicksight.list_users using NextToken and buffer all users
    in memory before returning

    Input: AWS account ID and QuickSight namespace
    Output: List of user dicts as returned by the QuickSight API

    Any exception raised while calling ListUsers is logged and re-raised
    so that no S3 write is ever reached for a partial/failed listing.
    """
    users = []
    next_token = None

    try:
        while True:
            kwargs = {"AwsAccountId": account_id, "Namespace": namespace}
            if next_token:
                kwargs["NextToken"] = next_token

            resp = quicksight.list_users(**kwargs)
            users.extend(resp.get("UserList", []))

            next_token = resp.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        print(f"Error calling QuickSight ListUsers: {str(e)}")
        traceback.print_exc()
        raise

    return users


def transform_user(user, account_id):
    """
    Transform a raw QuickSight user record into the snapshot row schema

    Input: A single user dict from the ListUsers response, and the account ID
    Output: Dict matching the licensed_users_snapshot table schema
    """
    return {
        "username": user.get("UserName", ""),
        "user_arn": user.get("Arn", ""),
        "email": user.get("Email", ""),
        "role": user.get("Role", ""),
        "identity_type": user.get("IdentityType", ""),
        "active": user.get("Active", False),
        "account_id": account_id,
    }


def build_snapshot_key(now):
    """
    Build the daily-partitioned S3 key for the snapshot file

    Input: A timezone-aware datetime
    Output: S3 key string of the form
        licensed-users-snapshot/year=YYYY/month=MM/day=DD/snapshot.json
    """
    return (
        f"licensed-users-snapshot/year={now.year}/"
        f"month={now.month:02d}/day={now.day:02d}/snapshot.json"
    )
