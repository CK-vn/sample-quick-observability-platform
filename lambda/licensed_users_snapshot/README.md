# Licensed Users Snapshot Lambda

Runs on a daily EventBridge schedule to paginate QuickSight `ListUsers`, then writes a single JSON Lines snapshot of all licensed users to S3 for Athena.

## Trigger

EventBridge scheduled rule (`cron(0 6 * * ? *)`), invoked with no meaningful input event.

## Environment Variables

- `AWS_ACCOUNT_ID` - AWS account ID passed to `quicksight.list_users`
- `DATA_LAKE_BUCKET` - S3 bucket the snapshot is written to
- `QUICKSIGHT_NAMESPACE` - QuickSight namespace to list users from (defaults to `default` if unset)

## Output Format

Single S3 object, JSON Lines (one JSON object per user):
```
s3://{DATA_LAKE_BUCKET}/licensed-users-snapshot/year=2024/month=01/day=15/snapshot.json
```
```json
{"username":"admin","user_arn":"arn:aws:quicksight:...:user/default/admin","email":"admin@example.com","role":"ADMIN","identity_type":"IAM","active":true,"account_id":"111122223333"}
```

## Logic

1. Call `quicksight.list_users`, following `NextToken` until exhausted, buffering all users in memory
2. Map each user to a snapshot record (username, ARN, email, role, identity type, active flag, account ID)
3. Write every record as one `put_object` call to `licensed-users-snapshot/year=YYYY/month=MM/day=DD/snapshot.json`, keyed by the current UTC date

## Error Handling

- `ListUsers` failures are logged and re-raised before any S3 write is attempted, so a failed run never produces a partial or corrupted snapshot
- All users are buffered before the single `put_object` call, ensuring the snapshot for a given day is all-or-nothing
