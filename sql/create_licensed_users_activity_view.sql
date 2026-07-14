-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
-- SPDX-License-Identifier: MIT-0
-- Licensed Users Activity view
-- Joins the latest snapshot of licensed users against last-activity across
-- chat_activity, agent_hours_usage, index_usage, and api_audit_trail, with a
-- first-seen-date proxy for account creation date
CREATE OR REPLACE VIEW ${DATABASE}.licensed_users_activity AS
WITH latest_snapshot_date AS (
    SELECT MAX(CAST(format('%04d-%02d-%02d', year, month, day) AS DATE)) AS max_date
    FROM ${DATABASE}.licensed_users_snapshot
),
current_users AS (
    SELECT s.username, s.user_arn, s.email, s.role, s.account_id
    FROM ${DATABASE}.licensed_users_snapshot s, latest_snapshot_date d
    WHERE CAST(format('%04d-%02d-%02d', s.year, s.month, s.day) AS DATE) = d.max_date
),
first_seen AS (
    SELECT username,
           MIN(CAST(format('%04d-%02d-%02d', year, month, day) AS DATE)) AS first_seen_date
    FROM ${DATABASE}.licensed_users_snapshot
    GROUP BY username
),
activity AS (
    SELECT user_name, event_time FROM ${DATABASE}.chat_activity
    UNION ALL
    SELECT user_name, event_time FROM ${DATABASE}.agent_hours_usage
    UNION ALL
    SELECT user_name, event_time FROM ${DATABASE}.index_usage
    UNION ALL
    SELECT user_name, event_time FROM ${DATABASE}.api_audit_trail
),
last_activity AS (
    SELECT user_name, MAX(event_time) AS last_activity_timestamp
    FROM activity
    GROUP BY user_name
)
SELECT
    u.username AS user_name,
    u.user_arn,
    u.email,
    u.role,
    la.last_activity_timestamp,
    fs.first_seen_date,
    date_diff('day',
        COALESCE(la.last_activity_timestamp, CAST(fs.first_seen_date AS TIMESTAMP)),
        CURRENT_TIMESTAMP
    ) AS inactivity_period,
    u.account_id
FROM current_users u
LEFT JOIN last_activity la ON la.user_name = u.username
LEFT JOIN first_seen fs ON fs.username = u.username;
