-- Rollback script for OEM Messaging Schema
-- Use this if you need to remove the OEM messaging tables

-- Drop views first
DROP VIEW IF EXISTS oem_vs_media_comparison CASCADE;

-- Drop function
DROP FUNCTION IF EXISTS get_oem_messaging_json(UUID);

-- Drop tables in reverse order (due to foreign keys)
DROP TABLE IF EXISTS message_pull_through CASCADE;
DROP TABLE IF EXISTS oem_competitive_positioning CASCADE;
DROP TABLE IF EXISTS oem_purchase_drivers CASCADE;
DROP TABLE IF EXISTS oem_brand_attributes CASCADE;
DROP TABLE IF EXISTS oem_key_features CASCADE;
DROP TABLE IF EXISTS oem_model_messaging CASCADE;
DROP TABLE IF EXISTS oem_messaging_sources CASCADE;

-- Drop indexes (if they weren't cascade dropped)
DROP INDEX IF EXISTS idx_oem_model_messaging_make_model;
DROP INDEX IF EXISTS idx_oem_key_features_model;
DROP INDEX IF EXISTS idx_oem_brand_attributes_model;
DROP INDEX IF EXISTS idx_oem_purchase_drivers_model;
DROP INDEX IF EXISTS idx_message_pull_through_clip;
DROP INDEX IF EXISTS idx_message_pull_through_model;