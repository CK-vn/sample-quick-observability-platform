# Deployment Notes — Lessons from a Real Deployment

Findings from deploying this repo end-to-end (Steps 1-4) to a live AWS account.
Intended for system admins and AI agents deploying this stack elsewhere. The
repo's own README and troubleshooting table cover the happy path; this file
covers what actually broke and why, plus the diagnostic approach that found
each root cause.

## Deployment example

Deployed with a custom resource prefix, a non-default AWS CLI profile, IAM
access control (no Lake Formation), and message content logging enabled.
Steps 1-4 all completed successfully after the fixes below.

## Issue 1: CloudWatchLogsRole missing KMS permissions (Step 2 — Pipeline)

**Symptom**: `AWS::Logs::SubscriptionFilter` creation fails on all 4 log-group
subscriptions with:

```
Could not deliver test message to specified Firehose stream. ... The grant for
the CMK ... to this delivery stream might have been revoked or caller might
not have sufficient permissions for the CMK.
```

**Wrong first guess**: looks like a KMS grant propagation race (Firehose
reports `CREATE_COMPLETE` before its CMK grant is usable). Retrying with
`cdk deploy --no-rollback` and waiting did **not** fix it — failed identically
4 times over 15+ minutes. That repetition is the signal it's not a race.

**Actual root cause**: `CloudWatchLogsRole` (the role CloudWatch Logs assumes
to call `firehose:PutRecord`/`PutRecordBatch` when creating a subscription
filter, including for the one-time CloudFormation test message) was granted
Firehose actions but **no KMS permissions** on the CMK. `firehose_role` had
the KMS grant; `cloudwatch_logs_role` did not.

**How it was found**: KMS grants existed and `PutRecord` worked fine with
admin credentials — ruling out a KMS/Firehose-side issue. Tried
`sts assume-role` on `CloudWatchLogsRole` directly, got `AccessDenied` (as
expected, only the service can assume it), which redirected attention to the
role's own policy — it had Firehose actions but no KMS.

**Fix** (already applied in `cdk/pipeline_stack.py`): added a policy statement
to `cloudwatch_logs_role` granting `kms:Decrypt`, `kms:Encrypt`,
`kms:GenerateDataKey` on the data lake CMK, mirroring `firehose_role`'s grant.

**Takeaway**: when a CloudFormation resource creation fails with the same
error on retry — even after `--no-rollback` and waiting — stop retrying and
diagnose. Check every IAM role in the chain, not just the obvious one.

## Issue 2: Orphaned S3 bucket blocks retry after pipeline rollback

**Symptom**: after a `ROLLBACK_COMPLETE`, the next `cdk deploy` fails
immediately with:

```
Resource of type 'AWS::S3::Bucket' with identifier '{prefix}-pipeline-datalake-{account}'
already exists.
```

**Cause**: `DataLakeBucket` has `RemovalPolicy.RETAIN` by design (data
safety). CloudFormation rollback deletes everything else but leaves the
bucket behind, which then collides with the bucket name on the next attempt.

**Fix**: verify the bucket is empty (`s3api list-object-versions`), then
`aws s3api delete-bucket` before retrying. Only safe to do this when you know
the previous deploy failed before any real data was written — check first,
don't assume.

## Issue 3: QuickSight can't query Athena — "not authorized: athena:StartQueryExecution" (Step 4 — Dashboard)

This was the hardest one — it took two distinct fixes because there are two
independent QuickSight-specific permission layers on top of standard IAM,
and IAM policy simulation says "allowed" the whole time because it only
evaluates identity/resource policies, not QuickSight's own internal layers.

**Symptom**: `AWS::QuickSight::DataSource` (Athena) fails its connection test:

```
Connection test failed: Could not get query execution ID: You are not
authorized to perform: athena:StartQueryExecution on the resource.
```

### Layer 1: QuickSight's S3 bucket allow-list

QuickSight maintains its own customer-managed IAM policy
(`AWSQuickSightS3Policy`, attached to `aws-quicksight-service-role-v0`) that
allow-lists specific S3 buckets. This is what the console's **Manage
QuickSight → Security & permissions → AWS resources → S3** toggle actually
edits. New buckets (the data lake, the Athena results bucket) are **not**
automatically added — you must add them yourself, either through the console
toggle or by editing the policy directly via IAM (`create-policy-version`,
mind the 5-version limit — delete the oldest version first if at the cap).

### Layer 2: Account-level QuickSight IAM Policy Assignment acting as a session policy

Even after fixing the S3 allow-list, the exact same error persisted twice in
a row. `aws iam simulate-principal-policy` against the service role for
`athena:StartQueryExecution` returned `allowed` — meaning the identity policy
was fine. This mismatch (IAM says allowed, real call denied) is the signature
of a restriction QuickSight applies internally, not a standard IAM policy.

Found via:

```bash
aws quicksight list-iam-policy-assignments --aws-account-id <acct> --namespace default --assignment-status ENABLED
aws quicksight describe-iam-policy-assignment --aws-account-id <acct> --namespace default --assignment-name <name>
```

The account had a pre-existing IAM Policy Assignment, unrelated to this
project, scoped to `group=["*"], user=["*"]` (i.e. every user/group in the
account) and pointing at a narrow AWS-managed policy (in this case
`AmazonS3FullAccess`). **QuickSight IAM Policy Assignments act as a session
policy** on top of the service role — session policies *intersect* with the
role's permissions, they don't add to them. A narrow, account-wide session
policy like this silently caps every QuickSight-initiated AWS call to
whatever it allows, blocking Athena regardless of what the service role's
own attached policies allow.

**Fix applied**: rather than disabling the pre-existing assignment (which
could break whatever it was originally set up for) or leaving it broken,
created a new managed policy that is a superset of the original policy plus
the Athena/Glue/KMS actions this dashboard needs, and updated the assignment
to point at the new policy instead. Preserves whatever the original
assignment granted, unblocks this dashboard's Athena access.

**Takeaway for future deployments**: if Athena/S3 access appears correctly
granted via IAM but QuickSight still gets `AccessDenied`, always check
`list-iam-policy-assignments` before assuming a propagation delay or
suspecting the wrong role. This is very easy to miss because:
- It's invisible to `simulate-principal-policy` (identity-policy only).
- It's account-wide and can be set up by anyone with QuickSight admin rights,
  for a completely unrelated purpose, long before this repo is ever deployed.
- The QuickSight console UI for this ("Manage QuickSight" as an *account*
  setting) is easy to overlook since it's not part of this repo's docs.
- Before changing or disabling any pre-existing assignment found this way,
  confirm with the account owner what it's used for — broadening the
  assigned policy (rather than disabling the assignment) is usually the
  safer option since it preserves existing access for whoever relies on it.

## Issue 4: No Lake Formation admin → use IAM access control instead

`deploy.py --datacatalog` defaults to Lake Formation, but that requires the
deploying identity to already be a Lake Formation administrator (checked via
`aws lakeformation get-data-lake-settings` → `DataLakeAdmins`). Making an
identity an LF admin is an account-wide change with broad blast radius (it
affects every Lake Formation-governed resource in the account, not just this
project) — don't do this without asking. Choosing IAM access control
(`--access-control iam` on `setup_datacatalog.py`) avoids the need entirely
and is fully supported by the repo.

## Issue 5: No Athena query-results bucket / workgroup output location

The target workgroup had no `ResultConfiguration.OutputLocation` configured,
and no existing bucket was clearly meant for this purpose. Created a
dedicated bucket (`{prefix}-athena-results-{account}`, encrypted, public
access blocked) rather than reusing an unrelated existing bucket. Remember to
also add this bucket to `AWSQuickSightS3Policy` (see Issue 3) if Quick Sight
will read query results from it.

## Issue 6: Dashboard shows "No data" even though Athena has rows

**Symptom**: Athena queries return real rows (confirmed via CLI/console), but
the Quick Sight dashboard still shows 0 / "No data" on every visual.

**Cause**: Quick Sight datasets in this stack use **SPICE** (an imported,
cached snapshot), not a live/direct query. If the SPICE ingestion ran before
any Quick activity existed, it cached an empty result and won't reflect new
rows until the next refresh. The stack's refresh schedule is daily
(06:00 UTC) — after a same-day deployment, that can mean a long wait before
the dashboard updates on its own.

**Fix**: trigger a manual refresh per dataset and confirm rows landed:

```bash
aws quicksight create-ingestion \
  --aws-account-id <acct> --data-set-id <prefix>-chat-activity \
  --ingestion-id manual-refresh-$(date +%s)

aws quicksight list-ingestions \
  --aws-account-id <acct> --data-set-id <prefix>-chat-activity \
  --max-results 1 \
  --query "Ingestions[0].[IngestionStatus,RowInfo.RowsIngested,RowInfo.TotalRowsInDataset]"
```

Repeat for each dataset (`chat-activity`, `feedback-analysis`,
`agent-hours-usage`, `api-audit-trail`, `index-usage`). Note that
`api-audit-trail` depends on CloudTrail, which has its own delivery delay
(typically several minutes) independent of the Firehose buffer setting —
don't expect it to populate as fast as the CloudWatch Logs-based tables.

**Takeaway**: after generating test activity, always trigger a manual SPICE
refresh rather than assuming the dashboard will reflect new data immediately
or on its default schedule.

## Performance tuning: Firehose buffer interval for testing

Default Firehose buffering (`128 MB` / `900s`) means up to 15 minutes between
generating Quick activity and seeing it in S3/Athena. For testing, this was
reduced to `1 MB` / `60s` (AWS minimums) in `cdk/pipeline_stack.py`
(`create_firehose_stream` helper, `BufferingHintsProperty`). Cost impact is
negligible at low/test volume — Firehose bills per GB ingested (not per
flush), Lambda invocations and S3 PUTs increase but stay in fractions of a
cent for testing traffic. **Revert to larger values (e.g. 128 MB / 900s)
before sustained production use** — frequent small files increase S3 request
costs and hurt Athena scan performance ("small file problem") over time.

## General diagnostic approach that worked

1. Don't retry a failed CloudFormation resource more than twice with the
   same inputs. Identical failures on retry mean the cause is deterministic,
   not a race — stop and diagnose.
2. `aws iam simulate-principal-policy` proves whether standard IAM allows an
   action. If it says `allowed` but the real call is still denied, the
   restriction lives somewhere IAM simulation doesn't see — for QuickSight,
   check `list-iam-policy-assignments` next.
3. `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=<action>`
   shows the exact denied call, including which role/session made it — use
   this to confirm which identity is actually failing before changing policy
   on the wrong resource.
4. When `cdk deploy` rolls back, check for orphaned `RemovalPolicy.RETAIN`
   resources (S3 buckets, KMS keys) before retrying — they can block resource
   creation on the next attempt with a name collision.
5. Use `--no-rollback` to preserve successfully-created resources when
   diagnosing a partial failure, so you're not re-creating everything (and
   re-hitting the same timing/ordering conditions) on every retry.
6. Remember SPICE datasets are snapshots. If the backend data is confirmed
   correct but a dashboard still looks empty or stale, refresh the dataset
   before assuming there's a pipeline problem.
