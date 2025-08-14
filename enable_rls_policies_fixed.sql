-- Enable Row Level Security and Create Policies for DriveShop Tables
-- This script handles views separately from tables
-- Run this script in your Supabase SQL editor

-- First, let's check which objects are views vs tables
SELECT 
    schemaname,
    tablename as object_name,
    'table' as object_type
FROM pg_tables 
WHERE schemaname = 'public'
UNION ALL
SELECT 
    schemaname,
    viewname as object_name,
    'view' as object_type
FROM pg_views 
WHERE schemaname = 'public'
ORDER BY object_type, object_name;

-- ============================================
-- TABLES ONLY (RLS can be applied)
-- ============================================

-- 1. CLIPS TABLE
ALTER TABLE public.clips ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read clips" ON public.clips
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to clips" ON public.clips
    FOR ALL TO service_role
    USING (true);

-- 2. CLIPS_DASHBOARD_ERRORS TABLE (if it's a table)
-- Check if it's a table first
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'clips_dashboard_errors') THEN
        ALTER TABLE public.clips_dashboard_errors ENABLE ROW LEVEL SECURITY;
        
        CREATE POLICY "Allow authenticated users to read dashboard errors" ON public.clips_dashboard_errors
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to dashboard errors" ON public.clips_dashboard_errors
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- 3. CLIPS_EXPORT TABLE
ALTER TABLE public.clips_export ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read clips_export" ON public.clips_export
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to create exports" ON public.clips_export
    FOR INSERT TO authenticated
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to clips_export" ON public.clips_export
    FOR ALL TO service_role
    USING (true);

-- 4. CLIPS_SENTIMENT_ANALYSIS TABLE
ALTER TABLE public.clips_sentiment_analysis ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read sentiment analysis" ON public.clips_sentiment_analysis
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to sentiment analysis" ON public.clips_sentiment_analysis
    FOR ALL TO service_role
    USING (true);

-- 5. MESSAGE_PULLTHROUGH TABLE
ALTER TABLE public.message_pullthrough ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read message_pullthrough" ON public.message_pullthrough
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to message_pullthrough" ON public.message_pullthrough
    FOR ALL TO service_role
    USING (true);

-- 6. OEM_BRAND_ATTRIBUTES TABLE
ALTER TABLE public.oem_brand_attributes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read oem_brand_attributes" ON public.oem_brand_attributes
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to oem_brand_attributes" ON public.oem_brand_attributes
    FOR ALL TO service_role
    USING (true);

-- 7. OEM_COMPETITOR_MENTIONS TABLE
ALTER TABLE public.oem_competitor_mentions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read oem_competitor_mentions" ON public.oem_competitor_mentions
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to oem_competitor_mentions" ON public.oem_competitor_mentions
    FOR ALL TO service_role
    USING (true);

-- 8. OEM_KEY_FEATURES TABLE
ALTER TABLE public.oem_key_features ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read oem_key_features" ON public.oem_key_features
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to oem_key_features" ON public.oem_key_features
    FOR ALL TO service_role
    USING (true);

-- 9. OEM_MESSAGING TABLE
ALTER TABLE public.oem_messaging ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read oem_messaging" ON public.oem_messaging
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to oem_messaging" ON public.oem_messaging
    FOR ALL TO service_role
    USING (true);

-- 10. OEM_MODEL_MESSAGING TABLE
ALTER TABLE public.oem_model_messaging ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read oem_model_messaging" ON public.oem_model_messaging
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to oem_model_messaging" ON public.oem_model_messaging
    FOR ALL TO service_role
    USING (true);

-- 11. OEM_PURCHASE_INCENTIVES TABLE
ALTER TABLE public.oem_purchase_incentives ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read oem_purchase_incentives" ON public.oem_purchase_incentives
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to oem_purchase_incentives" ON public.oem_purchase_incentives
    FOR ALL TO service_role
    USING (true);

-- 12. OEM_VS_MEDIA TABLE
ALTER TABLE public.oem_vs_media ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read oem_vs_media" ON public.oem_vs_media
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to oem_vs_media" ON public.oem_vs_media
    FOR ALL TO service_role
    USING (true);

-- 13. RUN_STATS TABLE
ALTER TABLE public.run_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read run_stats" ON public.run_stats
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to insert run_stats" ON public.run_stats
    FOR INSERT TO authenticated
    WITH CHECK (true);

CREATE POLICY "Allow authenticated users to update run_stats" ON public.run_stats
    FOR UPDATE TO authenticated
    USING (true);

CREATE POLICY "Allow service role full access to run_stats" ON public.run_stats
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- HANDLE VIEWS SEPARATELY
-- ============================================
-- For the clips_dashboard view, we need to ensure the underlying tables have proper RLS
-- Views inherit permissions from their base tables

-- Grant permissions on the view itself (not RLS, just regular permissions)
GRANT SELECT ON public.clips_dashboard TO authenticated;
GRANT ALL ON public.clips_dashboard TO service_role;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Check which tables have RLS enabled (excluding views)
SELECT 
    t.schemaname, 
    t.tablename, 
    t.rowsecurity,
    CASE 
        WHEN v.viewname IS NOT NULL THEN 'VIEW (RLS not applicable)'
        WHEN t.rowsecurity THEN 'TABLE (RLS enabled)'
        ELSE 'TABLE (RLS disabled)'
    END as status
FROM pg_tables t
LEFT JOIN pg_views v ON t.schemaname = v.schemaname AND t.tablename = v.viewname
WHERE t.schemaname = 'public'
ORDER BY t.tablename;

-- Check all policies created
SELECT schemaname, tablename, policyname, permissive, roles, cmd 
FROM pg_policies 
WHERE schemaname = 'public' 
ORDER BY tablename, policyname;

-- Check view permissions
SELECT 
    grantee,
    table_schema,
    table_name,
    privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public' 
    AND table_name = 'clips_dashboard'
ORDER BY grantee, privilege_type;