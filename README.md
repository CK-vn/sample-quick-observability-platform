# Amazon Quick Observability Platform

Terraform deployment for Amazon Quick observability. It collects chat, feedback, agent-hours, index-usage, and CloudTrail events into an encrypted S3 data lake, exposes Athena views, and creates a QuickSight dashboard and topic.

## Prerequisites

- Terraform 1.10+
- AWS CLI credentials for the target account and Region
- An active Amazon Quick/QuickSight subscription
- A QuickSight owner user ARN

Review [`docs/iam-policy.yaml`](docs/iam-policy.yaml) and [`docs/REQUIRED_PERMISSIONS.txt`](docs/REQUIRED_PERMISSIONS.txt) before deployment. The policy is a Terraform deployer baseline; Lambda and QuickSight runtime permissions are managed separately by Terraform.

## Deploy

1. Create the deployment input file and set `quicksight_owner_arn`:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

2. Initialize, review, and deploy:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform plan
terraform -chdir=terraform apply
```

Terraform deploys all infrastructure, the Athena catalog, QuickSight resources, and the supported topic datasets in one dependency graph. No separate deployment toolchain, bootstrap stack, or local deployment script is required. Chat `user_message` and `system_text_message` fields are collected into CloudWatch, S3, and Athena by default; set `include_message_content = false` to exclude them. The Chat Activity SPICE dataset and **Chat Session Details** table include `user_message` when collection is enabled. `system_text_message` remains outside QuickSight, and message content is not added to topics or Agent Hours because that log type has no message fields.

Useful outputs:

```bash
terraform -chdir=terraform output dashboard_arn
terraform -chdir=terraform output data_lake_bucket
```

`archive_file` generates reproducible ZIP artifacts in `terraform/` during plan/apply. Git ignores these artifacts, Terraform state, `.terraform/`, and `terraform.tfvars`.

## Architecture

![Terraform architecture](docs/sample-quick-observability-platform.png)

The deployment creates:

- KMS-encrypted CloudWatch log groups and vended-log delivery;
- Firehose streams and Lambda transforms that write CloudWatch and CloudTrail data to S3;
- an Athena workgroup, six tables, and eight views;
- seven hourly SPICE datasets, a six-sheet analysis/dashboard, and a topic using the five supported datasets;
- an hourly licensed-user snapshot Lambda.

The topic is ready for use in a manually created Amazon Quick Space or custom chat agent. Use [`docs/Quick custom chat agent.txt`](docs/Quick%20custom%20chat%20agent.txt) as the agent instruction prompt.

## Validate

Generate Quick activity, then verify delivery and data:

```bash
aws logs describe-deliveries --output table
aws s3 ls s3://<data-lake-bucket>/cloudwatch-logs/ --recursive
```

Firehose buffers at 1 MiB or 60 seconds; vended logs and CloudTrail add their own delivery latency. For deployment behavior, data-arrival details, and QuickSight troubleshooting, see [`docs/DEPLOYMENT_NOTES.md`](docs/DEPLOYMENT_NOTES.md).

## Destroy

Terraform blocks bucket and KMS-key deletion by default. For an approved full teardown: back up required data, set `force_destroy_buckets = true` and apply, remove the local `prevent_destroy` guards from `terraform/20-data-storage.tf` and `terraform/10-security-kms.tf`, then run:

```bash
terraform -chdir=terraform destroy
```

Never schedule deletion of the KMS key while encrypted data remains.

## Project structure

```text
terraform/                       Terraform root module and Lambda packaging
terraform/lambda/provisioner/    Catalog and QuickSight lifecycle provider
lambda/                          Data transform and snapshot Lambda sources
sql/                             Athena table and view definitions
docs/                            Deployment, architecture, and IAM review material
tests/                           Retained Lambda behavior tests
```

## References

- [Amazon Quick CloudWatch Logs](https://docs.aws.amazon.com/quick/latest/userguide/monitoring-quicksuite-chat-feedback-cloudwatch.html)
- [Amazon Quick CloudTrail monitoring](https://docs.aws.amazon.com/quick/latest/userguide/incident-response-logging-and-monitoring-qs.html)

## Contributing and license

See [CONTRIBUTING](CONTRIBUTING.md) and [LICENSE](LICENSE).
