-- Migration: Add cache tracking to workflow_executions
-- Created: 2026-01-19
-- Purpose: Track OpenAI prompt cache hits for cost optimization analysis

-- Add cache tracking columns
ALTER TABLE workflow_executions 
    ADD COLUMN IF NOT EXISTS llm_tokens_cached INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS llm_cache_hit_rate FLOAT DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS llm_cost_saved_usd FLOAT DEFAULT 0.0;

-- Add index for cost analysis queries
CREATE INDEX IF NOT EXISTS idx_workflow_executions_cost 
    ON workflow_executions(llm_cost_usd, llm_cost_saved_usd, created_at DESC);

-- Column comments for documentation
COMMENT ON COLUMN workflow_executions.llm_tokens_cached IS 
    'Total cached tokens served (from OpenAI prompt_tokens_details.cached_tokens). Cache activates at 1024+ token prompts.';

COMMENT ON COLUMN workflow_executions.llm_cache_hit_rate IS 
    'Cache hit rate percentage (cached_tokens / prompt_tokens * 100). Higher is better.';

COMMENT ON COLUMN workflow_executions.llm_cost_saved_usd IS 
    'Cost savings from cache hits in USD (uncached_cost - cached_cost). Discount: gpt-5-nano 90%, gpt-4.1 75%.';
