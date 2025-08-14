-- Add unique constraint to prevent duplicate OEM messaging entries
-- This ensures only one entry per make/model/year combination

ALTER TABLE oem_model_messaging 
ADD CONSTRAINT unique_make_model_year 
UNIQUE (make, model, year);

-- This will fail if duplicates already exist
-- First check for duplicates with:
-- SELECT make, model, year, COUNT(*) 
-- FROM oem_model_messaging 
-- GROUP BY make, model, year 
-- HAVING COUNT(*) > 1;