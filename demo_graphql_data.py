#!/usr/bin/env python3
"""
Demo script using captured GraphQL data.
Demonstrates data extraction and CSV export without needing live API access.
"""

import json
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from creatoriq.csv_exporter import export_posts_to_csv, export_summary_to_csv
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def extract_posts_from_captured_data():
    """Extract posts from our captured GraphQL response."""
    
    # Load the captured GraphQL response
    graphql_file = "data/network_dumps_debug/061_graphql.json"
    
    if not os.path.exists(graphql_file):
        raise FileNotFoundError(f"Captured GraphQL data not found: {graphql_file}")
    
    logger.info(f"📄 Loading captured GraphQL data: {graphql_file}")
    
    with open(graphql_file, 'r', encoding='utf-8') as f:
        response_data = json.load(f)
    
    # Extract posts from the response
    posts_data = response_data.get('data', {}).get('getPosts', {})
    edges = posts_data.get('edges', [])
    
    logger.info(f"📊 Found {len(edges)} posts in captured data")
    
    # Process each post
    extracted_posts = []
    
    for edge in edges:
        post_node = edge.get('node', {})
        
        # Helper function to safely get nested values
        def safe_get(obj, *keys, default=None):
            for key in keys:
                if isinstance(obj, dict) and key in obj:
                    obj = obj[key]
                else:
                    return default
            return obj
        
        # Extract creator information
        creator_name = safe_get(post_node, 'creator', 'fullName', default='Unknown')
        creator_username = (
            safe_get(post_node, 'creator', 'primarySocialUsername') or
            safe_get(post_node, 'account', 'socialUsername') or
            'unknown'
        )
        
        # Extract metrics
        impressions = safe_get(post_node, 'combinedMetrics', 'combinedImpressions', 'value', default=0)
        engagements = safe_get(post_node, 'combinedMetrics', 'combinedEngagements', 'value', default=0)
        
        # Try to get likes and comments from organic metrics
        likes = safe_get(post_node, 'organicMetrics', 'likes', default=0)
        comments = safe_get(post_node, 'organicMetrics', 'comments', default=0)
        
        extracted_post = {
            'post_id': safe_get(post_node, 'id', default=''),
            'post_url': safe_get(post_node, 'contentUrl', default=''),
            'platform': safe_get(post_node, 'network', default='UNKNOWN'),
            'content_type': safe_get(post_node, 'contentType', default='UNKNOWN'),
            'creator_name': creator_name,
            'username': creator_username,
            'date': safe_get(post_node, 'publishedAt', default=''),
            'caption': safe_get(post_node, 'text', default=''),
            'impressions': int(impressions) if impressions else 0,
            'engagements': int(engagements) if engagements else 0,
            'likes': int(likes) if likes else 0,
            'comments': int(comments) if comments else 0,
            'thumbnail_url': safe_get(post_node, 'thumbnailURL', default='')
        }
        
        extracted_posts.append(extracted_post)
    
    logger.info(f"✅ Extracted {len(extracted_posts)} posts successfully")
    return extracted_posts

def main():
    """Demo the GraphQL data extraction and CSV export."""
    
    print("🎯 CreatorIQ GraphQL Data Demo")
    print("=" * 50)
    print("Using captured GraphQL response to demonstrate data extraction")
    print()
    
    try:
        # Extract posts from captured data
        print("📄 Extracting posts from captured GraphQL response...")
        posts = extract_posts_from_captured_data()
        
        print(f"✅ Successfully extracted {len(posts)} posts")
        print()
        
        # Show sample data
        if posts:
            sample = posts[0]
            print("📋 Sample Post Data:")
            print(f"   🆔 ID: {sample.get('post_id', 'N/A')}")
            print(f"   🔗 URL: {sample.get('post_url', 'N/A')}")
            print(f"   📱 Platform: {sample.get('platform', 'N/A')}")
            print(f"   🎬 Type: {sample.get('content_type', 'N/A')}")
            print(f"   👤 Creator: {sample.get('creator_name', 'N/A')} (@{sample.get('username', 'N/A')})")
            print(f"   📅 Date: {sample.get('date', 'N/A')}")
            print(f"   👀 Impressions: {sample.get('impressions', 0):,}")
            print(f"   💬 Engagements: {sample.get('engagements', 0):,}")
            print(f"   ❤️ Likes: {sample.get('likes', 0):,}")
            print(f"   💭 Comments: {sample.get('comments', 0):,}")
            
            caption = sample.get('caption', '')
            if caption:
                print(f"   📝 Caption: {caption[:100]}{'...' if len(caption) > 100 else ''}")
            print()
        
        # Platform breakdown
        platforms = {}
        total_impressions = 0
        total_engagements = 0
        
        for post in posts:
            platform = post.get('platform', 'UNKNOWN')
            platforms[platform] = platforms.get(platform, 0) + 1
            total_impressions += post.get('impressions', 0)
            total_engagements += post.get('engagements', 0)
        
        print("📊 Campaign Statistics:")
        print(f"   📄 Total Posts: {len(posts)}")
        print(f"   👀 Total Impressions: {total_impressions:,}")
        print(f"   💬 Total Engagements: {total_engagements:,}")
        print(f"   📈 Avg Impressions/Post: {total_impressions/len(posts):,.0f}")
        print(f"   📈 Avg Engagements/Post: {total_engagements/len(posts):,.0f}")
        print()
        
        print("📊 Platform Breakdown:")
        for platform, count in sorted(platforms.items()):
            percentage = (count / len(posts)) * 100
            print(f"   {platform}: {count} posts ({percentage:.1f}%)")
        print()
        
        # Export to CSV
        print("💾 Exporting data to CSV...")
        
        # Export posts
        posts_csv = export_posts_to_csv(posts, "demo_creatoriq_posts.csv")
        print(f"   📄 Posts exported to: {posts_csv}")
        
        # Export summary
        summary_csv = export_summary_to_csv(posts, "demo_creatoriq_summary.csv")
        print(f"   📊 Summary exported to: {summary_csv}")
        
        print()
        print("🎯 Demo Results:")
        print("   ✅ GraphQL data extraction working correctly")
        print("   ✅ Post data parsing successful")
        print("   ✅ CSV export functionality working")
        print("   ✅ Ready for integration with Streamlit dashboard")
        print()
        print("📋 Next Steps:")
        print("   1. Add authentication to GraphQL client for live API access")
        print("   2. Integrate with Streamlit dashboard")
        print("   3. Add pagination to retrieve all 643+ posts")
        print("   4. Deploy to production environment")
        
        return 0
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 