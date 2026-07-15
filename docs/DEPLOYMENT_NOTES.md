# Deployment notes

These notes capture behavior verified during an end-to-end Terraform deployment. Terraform is the only deployment path in this repository.

## Verified deployment

A complete deployment was validated in `us-east-1` using an isolated resource prefix, IAM-based Glue/Athena access, and message-content collection enabled. The final `terraform plan` reported no changes.

The deployment creates:

- two KMS-encrypted S3 buckets and one managed Athena workgroup;
- four Amazon Quick vended-log groups and four Lambda log groups;
- five Firehose streams using 1 MiB / 60-second buffering;
- four Python 3.12 Lambda functions: two transforms, the licensed-user snapshot, and the Terraform provisioner;
- two EventBridge rules: Quick/CloudTrail routing and the hourly licensed-user snapshot at minute `55`;
- six Glue tables and eight Athena views;
- seven SPICE datasets with hourly full refresh schedules;
- a six-sheet analysis/dashboard and a topic containing the five datasets with supported topic mappings.

Terraform manages durable infrastructure directly. A small CloudFormation stack provides Create/Update/Delete lifecycle events to the provisioner Lambda, which owns Athena DDL and QuickSight resources. CloudFormation does not deploy the rest of the solution.

## Operational behavior

### Generated files

`archive_file` creates four reproducible ZIP packages in `terraform/` during plan/apply. They are ignored by Git along with `.terraform/`, `terraform.tfvars`, state, crash logs, and override files. Do not commit or share state or variable files.

### Data arrival and SPICE

A successful ingestion confirms that its query completed, not that it returned rows. Data appears only after the relevant Quick activity reaches S3/Athena. Firehose can flush low-volume data within about 60 seconds, while vended-log and CloudTrail delivery introduce independent latency.

Terraform schedules all seven SPICE datasets hourly. To test immediately, start a unique ingestion and inspect its terminal status and row count:

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

Repeat for `feedback-analysis`, `agent-hours-usage`, `api-audit-trail`, `index-usage`, `licensed-users`, or `function-usage-distribution` as appropriate. The licensed-user Lambda runs hourly but replaces the current UTC day's snapshot, so the table contains the latest snapshot for each day rather than hourly history.

Partition projection in the supplied SQL covers 2024–2030. Extend the projection range before 2031.

### Authorization boundaries

The Terraform deployer, provisioner Lambda, licensed-user Lambda, transform/streaming roles, and QuickSight service role are separate principals. The deployer installs runtime policies with `iam:PutRolePolicy`; it does not need the Glue DDL, QuickSight asset-management, SSM marker, S3 object, or KMS cryptographic actions used by runtime roles. See [`REQUIRED_PERMISSIONS.txt`](REQUIRED_PERMISSIONS.txt) and [`iam-policy.yaml`](iam-policy.yaml).

Terraform adds a deployment-specific inline policy to `aws-quicksight-service-role-v0`. If IAM simulation permits Athena but QuickSight still reports `AccessDenied`, inspect enabled QuickSight IAM policy assignments before changing role policies:

```bash
aws quicksight list-iam-policy-assignments \
  --aws-account-id <account-id> \
  --namespace default \
  --assignment-status ENABLED
```

### Teardown

A normal destroy is blocked by lifecycle guards. For an approved full deletion:

1. Back up required data.
2. Set `force_destroy_buckets = true` and apply.
3. Remove the local guards in `terraform/20-data-storage.tf` and `terraform/10-security-kms.tf`.
4. Run `terraform -chdir=terraform destroy`.

CloudFormation must invoke the provisioner during deletion. A QuickSight/Athena failure, stale ownership marker, or custom-resource timeout can block deletion. Never schedule KMS deletion while retained encrypted objects still depend on the key.
