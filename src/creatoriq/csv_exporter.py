"""
CreatorIQ CSV Exporter

Exports extracted post data to CSV format for analysis and integration.
"""

import csv
import os
from typing import List, Dict, Any
from datetime import datetime
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class CreatorIQCSVExporter:
    """
    CSV exporter for CreatorIQ post data.
    
    Handles formatting and exporting post data to CSV files.
    """
    
    def __init__(self):
        self.output_dir = "data"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _format_date(self, date_str: str) -> str:
        """
        Format ISO date string to readable format.
        
        Args:
            date_str: ISO date string
            
        Returns:
            Formatted date string
        """
        if not date_str:
            return ""
        
        try:
            # Parse ISO format: 2023-03-30T14:59:23.000Z
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return date_str
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text for CSV export (remove newlines, etc.).
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Replace newlines and tabs with spaces
        cleaned = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def export_to_csv(self, posts: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Export posts to CSV file.
        
        Args:
            posts: List of post dictionaries
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to exported CSV file
        """
        if not posts:
            raise ValueError("No posts to export")
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"creatoriq_posts_{timestamp}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        logger.info(f"📄 Exporting {len(posts)} posts to CSV: {filepath}")
        
        # Define CSV columns
        columns = [
            'post_id',
            'post_url',
            'platform',
            'content_type',
            'creator_name',
            'username',
            'date',
            'caption',
            'impressions',
            'engagements',
            'likes',
            'comments',
            'thumbnail_url'
        ]
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=columns)
                
                # Write header
                writer.writeheader()
                
                # Write posts
                for post in posts:
                    row = {
                        'post_id': post.get('post_id', ''),
                        'post_url': post.get('post_url', ''),
                        'platform': post.get('platform', ''),
                        'content_type': post.get('content_type', ''),
                        'creator_name': post.get('creator_name', ''),
                        'username': post.get('username', ''),
                        'date': self._format_date(post.get('date', '')),
                        'caption': self._clean_text(post.get('caption', '')),
                        'impressions': post.get('impressions', 0),
                        'engagements': post.get('engagements', 0),
                        'likes': post.get('likes', 0),
                        'comments': post.get('comments', 0),
                        'thumbnail_url': post.get('thumbnail_url', '')
                    }
                    writer.writerow(row)
            
            logger.info(f"✅ CSV export complete: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ CSV export failed: {e}")
            raise
    
    def export_summary(self, posts: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Export summary statistics to CSV.
        
        Args:
            posts: List of post dictionaries
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to exported summary CSV file
        """
        if not posts:
            raise ValueError("No posts to summarize")
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"creatoriq_summary_{timestamp}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        logger.info(f"📊 Generating summary for {len(posts)} posts: {filepath}")
        
        # Calculate statistics
        total_posts = len(posts)
        total_impressions = sum(post.get('impressions', 0) for post in posts)
        total_engagements = sum(post.get('engagements', 0) for post in posts)
        total_likes = sum(post.get('likes', 0) for post in posts)
        total_comments = sum(post.get('comments', 0) for post in posts)
        
        # Platform breakdown
        platforms = {}
        creators = {}
        
        for post in posts:
            platform = post.get('platform', 'UNKNOWN')
            creator = post.get('creator_name', 'Unknown')
            
            platforms[platform] = platforms.get(platform, 0) + 1
            creators[creator] = creators.get(creator, 0) + 1
        
        # Create summary data
        summary_data = [
            ['Metric', 'Value'],
            ['Total Posts', total_posts],
            ['Total Impressions', f"{total_impressions:,}"],
            ['Total Engagements', f"{total_engagements:,}"],
            ['Total Likes', f"{total_likes:,}"],
            ['Total Comments', f"{total_comments:,}"],
            ['Avg Impressions per Post', f"{total_impressions/total_posts:,.0f}" if total_posts > 0 else "0"],
            ['Avg Engagements per Post', f"{total_engagements/total_posts:,.0f}" if total_posts > 0 else "0"],
            ['', ''],  # Separator
            ['Platform Breakdown', ''],
        ]
        
        # Add platform breakdown
        for platform, count in sorted(platforms.items()):
            percentage = (count / total_posts) * 100 if total_posts > 0 else 0
            summary_data.append([f"  {platform}", f"{count} ({percentage:.1f}%)"])
        
        summary_data.extend([
            ['', ''],  # Separator
            ['Top Creators', ''],
        ])
        
        # Add top creators (top 10)
        top_creators = sorted(creators.items(), key=lambda x: x[1], reverse=True)[:10]
        for creator, count in top_creators:
            percentage = (count / total_posts) * 100 if total_posts > 0 else 0
            summary_data.append([f"  {creator}", f"{count} ({percentage:.1f}%)"])
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(summary_data)
            
            logger.info(f"✅ Summary export complete: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Summary export failed: {e}")
            raise

# Convenience functions
def export_posts_to_csv(posts: List[Dict[str, Any]], filename: str = None) -> str:
    """
    Convenience function to export posts to CSV.
    
    Args:
        posts: List of post dictionaries
        filename: Output filename (auto-generated if None)
        
    Returns:
        Path to exported CSV file
    """
    exporter = CreatorIQCSVExporter()
    return exporter.export_to_csv(posts, filename)

def export_summary_to_csv(posts: List[Dict[str, Any]], filename: str = None) -> str:
    """
    Convenience function to export summary to CSV.
    
    Args:
        posts: List of post dictionaries
        filename: Output filename (auto-generated if None)
        
    Returns:
        Path to exported summary CSV file
    """
    exporter = CreatorIQCSVExporter()
    return exporter.export_summary(posts, filename) 