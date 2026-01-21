-- Migration: Add location and timezone fields to users table
-- Date: 2026-01-18
-- Description: Adds default_location and timezone columns to support location-aware features

-- Add default_location column (e.g., "Nyíregyháza / Hungary")
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_location TEXT;

-- Add timezone column (e.g., "Europe/Budapest")
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT;

-- Add comment for documentation
COMMENT ON COLUMN users.default_location IS 'User''s default location in format "City / Country"';
COMMENT ON COLUMN users.timezone IS 'User''s timezone (IANA format, e.g., Europe/Budapest)';
