-- Enable Row Level Security ONLY for actual tables (not views)
-- This script first identifies what are tables vs views, then applies RLS accordingly

-- ============================================
-- STEP 1: IDENTIFY TABLES VS VIEWS
-- ============================================
-- Run this first to see what you're working with:

WITH objects AS (
    SELECT 
        tablename as name,
        'TABLE' as type
    FROM pg_tables 
    WHERE schemaname = 'public'
    
    UNION ALL
    
    SELECT 
        viewname as name,
        'VIEW' as type
    FROM pg_views 
    WHERE schemaname = 'public'
)
SELECT * FROM objects ORDER BY type, name;

-- ============================================
-- STEP 2: APPLY RLS ONLY TO ACTUAL TABLES
-- ============================================

-- Helper function to safely enable RLS only on tables
CREATE OR REPLACE FUNCTION enable_rls_if_table(table_name text) 
RETURNS void AS $$
BEGIN
    -- Check if it's actually a table (not a view)
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = table_name
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_views 
        WHERE schemaname = 'public' 
        AND viewname = table_name
    ) THEN
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        RAISE NOTICE 'RLS enabled for table: %', table_name;
    ELSE
        RAISE NOTICE 'Skipping % (not a table or is a view)', table_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Apply RLS to each object (will skip views automatically)
SELECT enable_rls_if_table('clips');
SELECT enable_rls_if_table('clips_dashboard');
SELECT enable_rls_if_table('clips_dashboard_errors');
SELECT enable_rls_if_table('clips_export');
SELECT enable_rls_if_table('clips_sentiment_analysis');
SELECT enable_rls_if_table('message_pullthrough');
SELECT enable_rls_if_table('oem_brand_attributes');
SELECT enable_rls_if_table('oem_competitor_mentions');
SELECT enable_rls_if_table('oem_key_features');
SELECT enable_rls_if_table('oem_messaging');
SELECT enable_rls_if_table('oem_model_messaging');
SELECT enable_rls_if_table('oem_purchase_incentives');
SELECT enable_rls_if_table('oem_vs_media');
SELECT enable_rls_if_table('run_stats');

-- Clean up the helper function
DROP FUNCTION enable_rls_if_table(text);

-- ============================================
-- STEP 3: CREATE POLICIES FOR TABLES THAT HAVE RLS ENABLED
-- ============================================

-- CLIPS TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'clips' 
        AND rowsecurity = true
    ) THEN
        -- Drop existing policies if any
        DROP POLICY IF EXISTS "Allow authenticated users to read clips" ON public.clips;
        DROP POLICY IF EXISTS "Allow service role full access to clips" ON public.clips;
        
        -- Create new policies
        CREATE POLICY "Allow authenticated users to read clips" ON public.clips
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to clips" ON public.clips
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- CLIPS_SENTIMENT_ANALYSIS TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'clips_sentiment_analysis' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read sentiment analysis" ON public.clips_sentiment_analysis;
        DROP POLICY IF EXISTS "Allow service role full access to sentiment analysis" ON public.clips_sentiment_analysis;
        
        CREATE POLICY "Allow authenticated users to read sentiment analysis" ON public.clips_sentiment_analysis
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to sentiment analysis" ON public.clips_sentiment_analysis
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- MESSAGE_PULLTHROUGH TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'message_pullthrough' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read message_pullthrough" ON public.message_pullthrough;
        DROP POLICY IF EXISTS "Allow service role full access to message_pullthrough" ON public.message_pullthrough;
        
        CREATE POLICY "Allow authenticated users to read message_pullthrough" ON public.message_pullthrough
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to message_pullthrough" ON public.message_pullthrough
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- OEM_BRAND_ATTRIBUTES TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'oem_brand_attributes' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read oem_brand_attributes" ON public.oem_brand_attributes;
        DROP POLICY IF EXISTS "Allow service role full access to oem_brand_attributes" ON public.oem_brand_attributes;
        
        CREATE POLICY "Allow authenticated users to read oem_brand_attributes" ON public.oem_brand_attributes
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to oem_brand_attributes" ON public.oem_brand_attributes
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- OEM_COMPETITOR_MENTIONS TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'oem_competitor_mentions' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read oem_competitor_mentions" ON public.oem_competitor_mentions;
        DROP POLICY IF EXISTS "Allow service role full access to oem_competitor_mentions" ON public.oem_competitor_mentions;
        
        CREATE POLICY "Allow authenticated users to read oem_competitor_mentions" ON public.oem_competitor_mentions
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to oem_competitor_mentions" ON public.oem_competitor_mentions
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- OEM_KEY_FEATURES TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'oem_key_features' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read oem_key_features" ON public.oem_key_features;
        DROP POLICY IF EXISTS "Allow service role full access to oem_key_features" ON public.oem_key_features;
        
        CREATE POLICY "Allow authenticated users to read oem_key_features" ON public.oem_key_features
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to oem_key_features" ON public.oem_key_features
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- OEM_MESSAGING TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'oem_messaging' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read oem_messaging" ON public.oem_messaging;
        DROP POLICY IF EXISTS "Allow service role full access to oem_messaging" ON public.oem_messaging;
        
        CREATE POLICY "Allow authenticated users to read oem_messaging" ON public.oem_messaging
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to oem_messaging" ON public.oem_messaging
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- OEM_MODEL_MESSAGING TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'oem_model_messaging' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read oem_model_messaging" ON public.oem_model_messaging;
        DROP POLICY IF EXISTS "Allow service role full access to oem_model_messaging" ON public.oem_model_messaging;
        
        CREATE POLICY "Allow authenticated users to read oem_model_messaging" ON public.oem_model_messaging
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to oem_model_messaging" ON public.oem_model_messaging
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- OEM_PURCHASE_INCENTIVES TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'oem_purchase_incentives' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read oem_purchase_incentives" ON public.oem_purchase_incentives;
        DROP POLICY IF EXISTS "Allow service role full access to oem_purchase_incentives" ON public.oem_purchase_incentives;
        
        CREATE POLICY "Allow authenticated users to read oem_purchase_incentives" ON public.oem_purchase_incentives
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to oem_purchase_incentives" ON public.oem_purchase_incentives
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- OEM_VS_MEDIA TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'oem_vs_media' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read oem_vs_media" ON public.oem_vs_media;
        DROP POLICY IF EXISTS "Allow service role full access to oem_vs_media" ON public.oem_vs_media;
        
        CREATE POLICY "Allow authenticated users to read oem_vs_media" ON public.oem_vs_media
            FOR SELECT TO authenticated
            USING (true);
        
        CREATE POLICY "Allow service role full access to oem_vs_media" ON public.oem_vs_media
            FOR ALL TO service_role
            USING (true);
    END IF;
END $$;

-- RUN_STATS TABLE (if RLS is enabled)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'run_stats' 
        AND rowsecurity = true
    ) THEN
        DROP POLICY IF EXISTS "Allow authenticated users to read run_stats" ON public.run_stats;
        DROP POLICY IF EXISTS "Allow authenticated users to insert run_stats" ON public.run_stats;
        DROP POLICY IF EXISTS "Allow authenticated users to update run_stats" ON public.run_stats;
        DROP POLICY IF EXISTS "Allow service role full access to run_stats" ON public.run_stats;
        
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
    END IF;
END $$;

-- ============================================
-- STEP 4: GRANT PERMISSIONS ON VIEWS
-- ============================================

-- For views, we use standard GRANT permissions (not RLS)
DO $$ 
BEGIN
    -- clips_dashboard view
    IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'clips_dashboard') THEN
        GRANT SELECT ON public.clips_dashboard TO authenticated;
        GRANT ALL ON public.clips_dashboard TO service_role;
        RAISE NOTICE 'Granted permissions on view: clips_dashboard';
    END IF;
    
    -- clips_export view
    IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'clips_export') THEN
        GRANT SELECT ON public.clips_export TO authenticated;
        GRANT ALL ON public.clips_export TO service_role;
        RAISE NOTICE 'Granted permissions on view: clips_export';
    END IF;
    
    -- clips_dashboard_errors (if it's a view)
    IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'clips_dashboard_errors') THEN
        GRANT SELECT ON public.clips_dashboard_errors TO authenticated;
        GRANT ALL ON public.clips_dashboard_errors TO service_role;
        RAISE NOTICE 'Granted permissions on view: clips_dashboard_errors';
    END IF;
END $$;

-- ============================================
-- STEP 5: FINAL VERIFICATION
-- ============================================

-- Show final status of all objects
SELECT 
    COALESCE(t.tablename, v.viewname) as object_name,
    CASE 
        WHEN v.viewname IS NOT NULL THEN 'VIEW'
        ELSE 'TABLE'
    END as object_type,
    CASE 
        WHEN v.viewname IS NOT NULL THEN 'N/A (Views use underlying table RLS)'
        WHEN t.rowsecurity = true THEN 'ENABLED'
        ELSE 'DISABLED'
    END as rls_status
FROM pg_tables t
FULL OUTER JOIN pg_views v 
    ON t.schemaname = v.schemaname 
    AND t.tablename = v.viewname
WHERE COALESCE(t.schemaname, v.schemaname) = 'public'
ORDER BY object_type, object_name;

-- Show all active policies
SELECT 
    tablename,
    policyname,
    cmd as operation,
    roles
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- Show view permissions
SELECT 
    table_name,
    grantee,
    string_agg(privilege_type, ', ') as privileges
FROM information_schema.table_privileges
WHERE table_schema = 'public' 
    AND table_name IN (
        SELECT viewname FROM pg_views WHERE schemaname = 'public'
    )
GROUP BY table_name, grantee
ORDER BY table_name, grantee;