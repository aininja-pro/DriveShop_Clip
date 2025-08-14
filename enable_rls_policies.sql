-- Enable Row Level Security and Create Policies for DriveShop Tables
-- Run this script in your Supabase SQL editor

-- ============================================
-- 1. CLIPS TABLE
-- ============================================
ALTER TABLE public.clips ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read all clips
CREATE POLICY "Allow authenticated users to read clips" ON public.clips
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role to manage clips (for backend operations)
CREATE POLICY "Allow service role full access to clips" ON public.clips
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 2. CLIPS_DASHBOARD TABLE
-- ============================================
ALTER TABLE public.clips_dashboard ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read dashboard data
CREATE POLICY "Allow authenticated users to read clips_dashboard" ON public.clips_dashboard
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to clips_dashboard" ON public.clips_dashboard
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 3. CLIPS_DASHBOARD_ERRORS TABLE
-- ============================================
ALTER TABLE public.clips_dashboard_errors ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read error logs
CREATE POLICY "Allow authenticated users to read dashboard errors" ON public.clips_dashboard_errors
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role to manage errors
CREATE POLICY "Allow service role full access to dashboard errors" ON public.clips_dashboard_errors
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 4. CLIPS_EXPORT TABLE
-- ============================================
ALTER TABLE public.clips_export ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read export data
CREATE POLICY "Allow authenticated users to read clips_export" ON public.clips_export
    FOR SELECT TO authenticated
    USING (true);

-- Allow authenticated users to create exports
CREATE POLICY "Allow authenticated users to create exports" ON public.clips_export
    FOR INSERT TO authenticated
    WITH CHECK (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to clips_export" ON public.clips_export
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 5. CLIPS_SENTIMENT_ANALYSIS TABLE
-- ============================================
ALTER TABLE public.clips_sentiment_analysis ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read sentiment analysis
CREATE POLICY "Allow authenticated users to read sentiment analysis" ON public.clips_sentiment_analysis
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to sentiment analysis" ON public.clips_sentiment_analysis
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 6. MESSAGE_PULLTHROUGH TABLE
-- ============================================
ALTER TABLE public.message_pullthrough ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read message data
CREATE POLICY "Allow authenticated users to read message_pullthrough" ON public.message_pullthrough
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to message_pullthrough" ON public.message_pullthrough
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 7. OEM_BRAND_ATTRIBUTES TABLE
-- ============================================
ALTER TABLE public.oem_brand_attributes ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read brand attributes
CREATE POLICY "Allow authenticated users to read oem_brand_attributes" ON public.oem_brand_attributes
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to oem_brand_attributes" ON public.oem_brand_attributes
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 8. OEM_COMPETITOR_MENTIONS TABLE
-- ============================================
ALTER TABLE public.oem_competitor_mentions ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read competitor mentions
CREATE POLICY "Allow authenticated users to read oem_competitor_mentions" ON public.oem_competitor_mentions
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to oem_competitor_mentions" ON public.oem_competitor_mentions
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 9. OEM_KEY_FEATURES TABLE
-- ============================================
ALTER TABLE public.oem_key_features ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read key features
CREATE POLICY "Allow authenticated users to read oem_key_features" ON public.oem_key_features
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to oem_key_features" ON public.oem_key_features
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 10. OEM_MESSAGING TABLE
-- ============================================
ALTER TABLE public.oem_messaging ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read messaging
CREATE POLICY "Allow authenticated users to read oem_messaging" ON public.oem_messaging
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to oem_messaging" ON public.oem_messaging
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 11. OEM_MODEL_MESSAGING TABLE
-- ============================================
ALTER TABLE public.oem_model_messaging ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read model messaging
CREATE POLICY "Allow authenticated users to read oem_model_messaging" ON public.oem_model_messaging
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to oem_model_messaging" ON public.oem_model_messaging
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 12. OEM_PURCHASE_INCENTIVES TABLE
-- ============================================
ALTER TABLE public.oem_purchase_incentives ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read purchase incentives
CREATE POLICY "Allow authenticated users to read oem_purchase_incentives" ON public.oem_purchase_incentives
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to oem_purchase_incentives" ON public.oem_purchase_incentives
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 13. OEM_VS_MEDIA TABLE
-- ============================================
ALTER TABLE public.oem_vs_media ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read vs media data
CREATE POLICY "Allow authenticated users to read oem_vs_media" ON public.oem_vs_media
    FOR SELECT TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to oem_vs_media" ON public.oem_vs_media
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- 14. RUN_STATS TABLE
-- ============================================
ALTER TABLE public.run_stats ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read run stats
CREATE POLICY "Allow authenticated users to read run_stats" ON public.run_stats
    FOR SELECT TO authenticated
    USING (true);

-- Allow authenticated users to insert run stats
CREATE POLICY "Allow authenticated users to insert run_stats" ON public.run_stats
    FOR INSERT TO authenticated
    WITH CHECK (true);

-- Allow authenticated users to update their own run stats
CREATE POLICY "Allow authenticated users to update run_stats" ON public.run_stats
    FOR UPDATE TO authenticated
    USING (true);

-- Allow service role full access
CREATE POLICY "Allow service role full access to run_stats" ON public.run_stats
    FOR ALL TO service_role
    USING (true);

-- ============================================
-- VERIFICATION QUERIES
-- ============================================
-- Run these queries after applying policies to verify RLS is enabled:

-- Check which tables have RLS enabled
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;

-- Check all policies created
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check 
FROM pg_policies 
WHERE schemaname = 'public' 
ORDER BY tablename, policyname;