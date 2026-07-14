# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Tests for cdk/pipeline_stack.py (PipelineStack)
"""
from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from cdk.pipeline_stack import PipelineStack


def _synth_template() -> Template:
    """Synthesize PipelineStack once with a mock kmsKeyArn context value
    (PipelineStack raises ValueError without it) and return its Template."""
    app = App(
        context={
            "kmsKeyArn": "arn:aws:kms:us-east-1:123456789012:key/mock-key-id",
        }
    )
    stack = PipelineStack(app, "TestPipelineStack", env={"account": "123456789012", "region": "us-east-1"})
    return Template.from_stack(stack)


# ---------------------------------------------------------------------------
# Task 5.5 - unit test asserting the IAM policy shape via aws_cdk.assertions.Template
# Requirements: 5.5
# ---------------------------------------------------------------------------
def test_licensed_users_snapshot_role_policy_is_least_privilege():
    """Requirements: 5.5 - the LicensedUsersSnapshotRole's DefaultPolicy grants
    exactly quicksight:ListUsers (Resource: "*"), the scoped s3:PutObject
    resource under licensed-users-snapshot/*, and the KMS encrypt/data-key
    actions on the data lake key -- no broader access."""
    template = _synth_template()

    policies = template.find_resources(
        "AWS::IAM::Policy",
        {
            "Properties": {
                "PolicyName": Match.string_like_regexp("LicensedUsersSnapshotRoleDefaultPolicy.*"),
            }
        },
    )
    assert len(policies) == 1, "expected exactly one LicensedUsersSnapshotRole DefaultPolicy"

    policy_document = list(policies.values())[0]["Properties"]["PolicyDocument"]
    statements = policy_document["Statement"]
    assert len(statements) == 3, f"expected exactly 3 statements, got {len(statements)}"

    actions_seen = set()
    for statement in statements:
        assert statement["Effect"] == "Allow"
        actions = statement["Action"]
        actions = [actions] if isinstance(actions, str) else actions
        actions_seen.update(actions)

        if "quicksight:ListUsers" in actions:
            assert actions == ["quicksight:ListUsers"]
            assert statement["Resource"] == "*"
        elif "s3:PutObject" in actions:
            assert actions == ["s3:PutObject"]
            resource = statement["Resource"]
            # Resource is a CFN intrinsic Fn::Join referencing the bucket
            # ARN plus the "/licensed-users-snapshot/*" suffix.
            joined_parts = resource["Fn::Join"][1]
            assert joined_parts[-1] == "/licensed-users-snapshot/*"
        elif "kms:Encrypt" in actions or "kms:GenerateDataKey" in actions:
            assert set(actions) == {"kms:Encrypt", "kms:GenerateDataKey"}
        else:
            raise AssertionError(f"unexpected policy statement actions: {actions}")

    # No broader access than exactly these three actions across all statements.
    assert actions_seen == {
        "quicksight:ListUsers",
        "s3:PutObject",
        "kms:Encrypt",
        "kms:GenerateDataKey",
    }
