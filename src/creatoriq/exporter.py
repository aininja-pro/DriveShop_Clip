import pandas as pd
from urllib.parse import urlparse
from src.utils.logger import setup_logger

# Use the existing DriveShop logger system
logger = setup_logger(__name__)

def get_platform(url):
    if 'instagram.com' in url:
        return 'Instagram'
    if 'tiktok.com' in url:
        return 'TikTok'
    if 'youtube.com' in url:
        return 'YouTube'
    if 'twitter.com' in url:
        return 'Twitter'
    if 'facebook.com' in url:
        return 'Facebook'
    return 'Unknown'

def export_to_csv(urls: list, filename: str):
    logger.info(f"📊 Starting CSV export for {len(urls)} URLs")
    logger.info(f"💾 Export filename: {filename}")
    
    data = []
    platform_counts = {}
    
    for i, url in enumerate(urls, 1):
        platform = get_platform(url)
        
        # Count platforms
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        data.append({
            "Creator": "",
            "Platform": platform,
            "Post Type": "",
            "Date": "",
            "Caption": "",
            "Post URL": url,
            "Views": "",
            "Likes": "",
            "Comments": "",
            "Shares": "",
            "Impressions": ""
        })
        
        # Log progress every 50 URLs
        if i % 50 == 0:
            logger.info(f"📝 Processed {i}/{len(urls)} URLs...")
    
    logger.info("📊 Platform breakdown:")
    for platform, count in platform_counts.items():
        logger.info(f"   {platform}: {count} URLs")
    
    logger.info("🔄 Creating DataFrame...")
    df = pd.DataFrame(data)
    
    logger.info(f"💾 Writing CSV to: {filename}")
    df.to_csv(filename, index=False)
    
    logger.info(f"✅ CSV export complete! {len(urls)} URLs saved to {filename}") 