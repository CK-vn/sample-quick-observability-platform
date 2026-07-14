-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
-- SPDX-License-Identifier: MIT-0
-- Function Usage Distribution view
-- Unions Chat Activity (System Chat Agent, Custom Chat Agent, Flow) with
-- Agent Hours Usage (Research, Flow, Automation) into a single set of
-- category-labeled rows for a combined percentage-of-total distribution.
-- Agent Hours' Chat service is deliberately excluded to avoid double-counting
-- chat usage already captured by Chat Activity.
CREATE OR REPLACE VIEW ${DATABASE}.function_usage_distribution AS
SELECT
    event_time, user_name,
    CASE WHEN feature LIKE 'System Chat Agent%' THEN 'System Chat Agent' ELSE feature END AS category,
    year, month, day
FROM ${DATABASE}.chat_activity
WHERE feature IN ('Flow', 'Custom Chat Agent') OR feature LIKE 'System Chat Agent%'
UNION ALL
SELECT
    event_time, user_name, resource_type AS category, year, month, day
FROM ${DATABASE}.agent_hours_usage
WHERE resource_type IN ('Research', 'Flow', 'Automation');
