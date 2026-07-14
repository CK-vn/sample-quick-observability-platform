# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Amazon Quick Observability Platform - Logs Stack

Creates:
- Customer-managed KMS key (with automatic rotation)
- CloudWatch Log Groups (chat, feedback, agent hours, index usage) - KMS encrypted
- Vended logs delivery configuration (sources, destinations, deliveries)
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_kms as kms,
    aws_logs as logs,
    aws_iam as iam,
)
from constructs import Construct


class LogsStack(Stack):
    """Stack for KMS encryption and CloudWatch Logs delivery."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        account_id = Stack.of(self).account
        region = Stack.of(self).region
        stack_name = Stack.of(self).stack_name
        resource_prefix = self.node.try_get_context("resourcePrefix") or "quickobserve"

        # Log group names from context or defaults
        chat_logs_group_name = self.node.try_get_context("chatLogsGroup") or "/aws/vendedlogs/quick/chat"
        feedback_logs_group_name = self.node.try_get_context("feedbackLogsGroup") or "/aws/vendedlogs/quick/feedback"
        agent_hours_logs_group_name = self.node.try_get_context("agentHoursLogsGroup") or "/aws/vendedlogs/quick/agent-hours"
        index_usage_logs_group_name = self.node.try_get_context("indexUsageLogsGroup") or "/aws/vendedlogs/quick/index-usage"

        # Whether to include user_message and system_text_message in chat logs.
        # Default is false — message content is excluded for enterprise environments
        # because it may contain data from connected enterprise sources.
        include_message_content = self.node.try_get_context("includeMessageContent") == "true"

        # ====================================================================
        # KMS Key
        # ====================================================================
        self.kms_key = kms.Key(
            self, "ObservabilityKey",
            alias=f"alias/{resource_prefix}-observability",
            description="Amazon Quick Observability Platform encryption key",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Allow delivery.logs.amazonaws.com to use the key for vended logs delivery
        self.kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogsDelivery",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("delivery.logs.amazonaws.com")],
                actions=["kms:GenerateDataKey", "kms:Decrypt"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "kms:EncryptionContext:SourceArn": f"arn:aws:logs:{region}:{account_id}:*"
                    }
                },
            )
        )

        # Allow logs.amazonaws.com to use the key for CloudWatch Log Group encryption
        self.kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogsEncryption",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal(f"logs.{region}.amazonaws.com")],
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
                conditions={
                    "ArnLike": {
                        "kms:EncryptionContext:aws:logs:arn": f"arn:aws:logs:{region}:{account_id}:*"
                    }
                },
            )
        )

        # Allow Quick Sight service role to decrypt data lake objects
        self.kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowQuickSightDecrypt",
                effect=iam.Effect.ALLOW,
                principals=[iam.ArnPrincipal(f"arn:aws:iam::{account_id}:role/service-role/aws-quicksight-service-role-v0")],
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        # ====================================================================
        # CloudWatch Log Groups
        # ====================================================================

        self.chat_log_group = logs.LogGroup(
            self, "ChatLogGroup",
            log_group_name=chat_logs_group_name,
            encryption_key=self.kms_key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.feedback_log_group = logs.LogGroup(
            self, "FeedbackLogGroup",
            log_group_name=feedback_logs_group_name,
            encryption_key=self.kms_key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.agent_hours_log_group = logs.LogGroup(
            self, "AgentHoursLogGroup",
            log_group_name=agent_hours_logs_group_name,
            encryption_key=self.kms_key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.index_usage_log_group = logs.LogGroup(
            self, "IndexUsageLogGroup",
            log_group_name=index_usage_logs_group_name,
            encryption_key=self.kms_key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ====================================================================
        # Vended Logs Delivery Configuration
        # ====================================================================
        quicksight_arn = f"arn:aws:quicksight:{region}:{account_id}:account/{account_id}"

        # Chat logs delivery
        chat_source = logs.CfnDeliverySource(
            self, "ChatDeliverySource",
            name=f"{resource_prefix}-chat-logs",
            log_type="CHAT_LOGS",
            resource_arn=quicksight_arn,
        )

        chat_dest = logs.CfnDeliveryDestination(
            self, "ChatDeliveryDestination",
            name=f"{resource_prefix}-chat-destination",
            output_format="json",
            destination_resource_arn=self.chat_log_group.log_group_arn,
        )
        chat_dest.add_dependency(self.chat_log_group.node.default_child)

        chat_delivery = logs.CfnDelivery(
            self, "ChatDelivery",
            delivery_source_name=chat_source.name,
            delivery_destination_arn=chat_dest.attr_arn,
            record_fields=[
                "user_arn", "user_type", "status_code", "conversation_id",
                "system_message_id", "user_message_id",
                "agent_id", "flow_id", "message_scope",
                "user_selected_resources", "action_connectors", "cited_resource",
                "file_attachment", "resource_arn", "event_timestamp", "logType",
                "accountId", "namespace", "latency", "time_to_first_token",
                "surface_type", "web_search",
            ] + (["user_message", "system_text_message"] if include_message_content else []),
        )
        chat_delivery.add_dependency(chat_source)
        chat_delivery.add_dependency(chat_dest)

        # Feedback logs delivery
        feedback_source = logs.CfnDeliverySource(
            self, "FeedbackDeliverySource",
            name=f"{resource_prefix}-feedback-logs",
            log_type="FEEDBACK_LOGS",
            resource_arn=quicksight_arn,
        )

        feedback_dest = logs.CfnDeliveryDestination(
            self, "FeedbackDeliveryDestination",
            name=f"{resource_prefix}-feedback-destination",
            output_format="json",
            destination_resource_arn=self.feedback_log_group.log_group_arn,
        )
        feedback_dest.add_dependency(self.feedback_log_group.node.default_child)

        feedback_delivery = logs.CfnDelivery(
            self, "FeedbackDelivery",
            delivery_source_name=feedback_source.name,
            delivery_destination_arn=feedback_dest.attr_arn,
            record_fields=[
                "user_arn", "user_type", "status_code", "conversation_id",
                "system_message_id", "user_message_id", "research_id",
                "feedback_type", "feedback_reason", "feedback_details",
                "rating", "resource_arn", "event_timestamp", "logType",
                "accountId", "namespace",
            ],
        )
        feedback_delivery.add_dependency(feedback_source)
        feedback_delivery.add_dependency(feedback_dest)

        # Agent hours logs delivery
        agent_hours_source = logs.CfnDeliverySource(
            self, "AgentHoursDeliverySource",
            name=f"{resource_prefix}-agent-hours-logs",
            log_type="AGENT_HOURS_LOGS",
            resource_arn=quicksight_arn,
        )

        agent_hours_dest = logs.CfnDeliveryDestination(
            self, "AgentHoursDeliveryDestination",
            name=f"{resource_prefix}-agent-hours-destination",
            output_format="json",
            destination_resource_arn=self.agent_hours_log_group.log_group_arn,
        )
        agent_hours_dest.add_dependency(self.agent_hours_log_group.node.default_child)

        agent_hours_delivery = logs.CfnDelivery(
            self, "AgentHoursDelivery",
            delivery_source_name=agent_hours_source.name,
            delivery_destination_arn=agent_hours_dest.attr_arn,
            record_fields=[
                "user_arn", "subscription_type", "reporting_service",
                "usage_group", "usage_hours", "service_resource_arn",
                "resource_arn", "event_timestamp", "logType", "accountId",
            ],
        )
        agent_hours_delivery.add_dependency(agent_hours_source)
        agent_hours_delivery.add_dependency(agent_hours_dest)

        # Index usage logs delivery
        index_usage_source = logs.CfnDeliverySource(
            self, "IndexUsageDeliverySource",
            name=f"{resource_prefix}-index-usage-logs",
            log_type="INDEX_USAGE_LOGS",
            resource_arn=quicksight_arn,
        )

        index_usage_dest = logs.CfnDeliveryDestination(
            self, "IndexUsageDeliveryDestination",
            name=f"{resource_prefix}-index-usage-destination",
            output_format="json",
            destination_resource_arn=self.index_usage_log_group.log_group_arn,
        )
        index_usage_dest.add_dependency(self.index_usage_log_group.node.default_child)

        index_usage_delivery = logs.CfnDelivery(
            self, "IndexUsageDelivery",
            delivery_source_name=index_usage_source.name,
            delivery_destination_arn=index_usage_dest.attr_arn,
            # INDEX_USAGE_LOGS uses snake_case for common fields (log_type,
            # account_id) unlike older log types which use camelCase (logType,
            # accountId).  Omitting record_fields entirely delivers all fields
            # by default, but we list them explicitly for clarity.
            record_fields=[
                "resource_arn", "event_timestamp", "log_type", "account_id",
                "user_arn", "consumed_index_size", "source_type",
                "source_name", "source_arn", "consumed_source_size",
                "consumed_source_doc_count",
            ],
        )
        index_usage_delivery.add_dependency(index_usage_source)
        index_usage_delivery.add_dependency(index_usage_dest)

        # ====================================================================
        # Outputs
        # ====================================================================
        CfnOutput(self, "KmsKeyArn", value=self.kms_key.key_arn,
                  description="KMS key ARN for data encryption")
        CfnOutput(self, "ChatLogsGroup", value=chat_logs_group_name,
                  description="Chat logs CloudWatch Log Group name")
        CfnOutput(self, "FeedbackLogsGroup", value=feedback_logs_group_name,
                  description="Feedback logs CloudWatch Log Group name")
        CfnOutput(self, "AgentHoursLogsGroup", value=agent_hours_logs_group_name,
                  description="Agent hours logs CloudWatch Log Group name")
        CfnOutput(self, "IndexUsageLogsGroup", value=index_usage_logs_group_name,
                  description="Index usage logs CloudWatch Log Group name")
        CfnOutput(self, "IncludeMessageContent",
                  value="true" if include_message_content else "false",
                  description="Whether chat message content is included in logs")
