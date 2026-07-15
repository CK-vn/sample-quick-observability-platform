# Deployment notes

Terraform is the only deployment path in this repository. It provisions the infrastructure, Athena catalog, QuickSight assets, and lifecycle bridge as one dependency graph.

## First deployment

1. Review [`iam-policy.yaml`](iam-policy.yaml) and [`REQUIRED_PERMISSIONS.txt`](REQUIRED_PERMISSIONS.txt).
2. Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`.
3. Set the target Region, a unique `resource_prefix`, and a valid QuickSight owner ARN. Do not commit `terraform.tfvars`.
4. Deploy:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform plan
terraform -chdir=terraform apply
```

The stack creates two encrypted S3 buckets, an Athena workgroup, vended-log delivery, Firehose streams, Lambda functions, EventBridge rules, the Athena catalog, seven SPICE datasets, and the QuickSight analysis, dashboard, and optional topic.

## Message content

`include_message_content` defaults to `true`. It collects `user_message` and `system_text_message` in the chat vended-log delivery, S3 data lake, and Athena `chat_logs` table.

The Chat Activity SPICE dataset and **Chat Session Details** table expose `user_message`. `system_text_message` is not exposed in QuickSight or the topic. **Agent Hours Details** cannot show message text because `AGENT_HOURS_LOGS` contains neither message fields nor a reliable conversation/message identifier. Set `include_message_content = false` before deployment when message content must not be collected.

## Data arrival and SPICE

Quick activity first reaches the data lake through vended-log delivery and Firehose. Low-volume Firehose data can flush within roughly 60 seconds; upstream delivery adds independent latency. An ingestion can succeed before matching records exist.

All seven SPICE datasets refresh hourly. To request an immediate Chat Activity refresh:

```bash
aws quicksight create-ingestion \
  --aws-account-id <account-id> \
  --data-set-id <resource-prefix>-chat-activity \
  --ingestion-id manual-$(date +%s)

aws quicksight list-ingestions \
  --aws-account-id <account-id> \
  --data-set-id <resource-prefix>-chat-activity \
  --max-results 1
```

Partition projection in the supplied SQL covers 2024–2030. Extend the range before 2031.

## Validate

After `apply`, retrieve the dashboard and storage outputs:

```bash
terraform -chdir=terraform output dashboard_arn
terraform -chdir=terraform output data_lake_bucket
terraform -chdir=terraform plan
```

Generate Quick activity, then confirm that objects arrive in the data lake and that the Chat Activity dataset has completed an ingestion. `terraform plan` should report no changes after the deployment stabilizes.

## Authorization boundaries

The Terraform deployer, provisioner Lambda, licensed-user snapshot Lambda, transform/streaming roles, and QuickSight Athena data-source run-as role are separate principals. Terraform installs scoped runtime policies using `iam:PutRolePolicy`; the deployer does not directly receive the runtime Glue, Athena, S3-object, KMS, or QuickSight asset actions.

The dedicated QuickSight Athena run-as role provides the Athena, Glue, S3, and KMS access required by the data source. It avoids reliance on the shared QuickSight service role's session policy.

## Teardown

Normal destruction is blocked by lifecycle guards on the two S3 buckets and KMS key. For an approved full teardown, back up required data, set `force_destroy_buckets = true` and apply it, remove the three local `prevent_destroy` guards in `terraform/20-data-storage.tf` and `terraform/10-security-kms.tf`, then run:

```bash
terraform -chdir=terraform destroy
```

Restore `force_destroy_buckets = false` and all three guards immediately afterward. Do not schedule KMS key deletion while encrypted retained data depends on the key.
