-- Migration: Add state_before and state_after columns
-- Date: 2026-01-18
-- Purpose: Replace single state_snapshot with separate before/after states for accurate tracking

BEGIN;

-- Add new columns (nullable for backward compatibility)
ALTER TABLE node_executions
ADD COLUMN IF NOT EXISTS state_before JSONB,
ADD COLUMN IF NOT EXISTS state_after JSONB;

-- Migrate existing data: state_snapshot → state_after (it was captured after node execution)
UPDATE node_executions
SET state_after = state_snapshot
WHERE state_snapshot IS NOT NULL AND state_after IS NULL;

-- Drop old column (optional - keep for rollback safety)
-- ALTER TABLE node_executions DROP COLUMN IF EXISTS state_snapshot;

COMMIT;

-- Verification query (run manually to check):
-- SELECT node_name, 
--        state_snapshot IS NOT NULL as has_old,
--        state_before IS NOT NULL as has_before,
--        state_after IS NOT NULL as has_after
-- FROM node_executions
-- LIMIT 10;
