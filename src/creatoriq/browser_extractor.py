#!/usr/bin/env python3
"""
CreatorIQ Browser Data Extractor

This script uses Playwright to load the CreatorIQ report page,
scroll through all posts, and extract the data directly from the DOM.
No authentication needed - just loads the public report URL.
"""

import asyncio
import json
import csv
from pathlib import Path
from playwright.async_api import async_playwright
import time

class CreatorIQBrowserExtractor:
    def __init__(self, report_url):
        self.report_url = report_url
        self.posts_data = []
        
    async def extract_all_posts(self):
        """
        Load the CreatorIQ report page and extract all post data
        """
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=False)  # Set to True to hide browser
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            
            page = await context.new_page()
            
            try:
                print(f"🌐 Loading CreatorIQ report: {self.report_url}")
                await page.goto(self.report_url, wait_until='networkidle')
                
                # Wait for initial content to load
                await page.wait_for_timeout(3000)
                
                print("📜 Starting infinite scroll to load all posts...")
                await self.scroll_and_load_all_posts(page)
                
                print("📊 Extracting post data from DOM...")
                await self.extract_posts_from_dom(page)
                
                print(f"✅ Successfully extracted {len(self.posts_data)} posts!")
                
            except Exception as e:
                print(f"❌ Error during extraction: {e}")
                
            finally:
                await browser.close()
                
        return self.posts_data
    
    async def scroll_and_load_all_posts(self, page):
        """
        Scroll through the page to trigger infinite scroll and load all posts
        """
        previous_post_count = 0
        no_change_count = 0
        max_no_change = 5  # Stop after 5 scrolls with no new posts
        
        while no_change_count < max_no_change:
            # Scroll to bottom
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            
            # Wait for new content to load
            await page.wait_for_timeout(2000)
            
            # Count current posts (adjust selector based on actual DOM structure)
            current_post_count = await page.locator('[data-testid*="post"], .post-item, [class*="post"]').count()
            
            if current_post_count == 0:
                # Try different selectors if no posts found
                current_post_count = await page.locator('article, .card, [class*="content"]').count()
            
            print(f"📈 Found {current_post_count} posts (was {previous_post_count})")
            
            if current_post_count > previous_post_count:
                previous_post_count = current_post_count
                no_change_count = 0  # Reset counter
            else:
                no_change_count += 1
                
            # Extra wait if we're still loading
            if no_change_count < max_no_change:
                await page.wait_for_timeout(1000)
    
    async def extract_posts_from_dom(self, page):
        """
        Extract post data from the loaded DOM
        """
        # Try multiple selectors to find posts
        post_selectors = [
            '[data-testid*="post"]',
            '.post-item',
            '[class*="post"]',
            'article',
            '.card',
            '[class*="content-item"]'
        ]
        
        posts_found = False
        
        for selector in post_selectors:
            posts = await page.locator(selector).all()
            if posts:
                print(f"🎯 Found {len(posts)} posts using selector: {selector}")
                posts_found = True
                
                for i, post in enumerate(posts):
                    try:
                        post_data = await self.extract_single_post_data(post, i)
                        if post_data:
                            self.posts_data.append(post_data)
                    except Exception as e:
                        print(f"⚠️ Error extracting post {i}: {e}")
                        continue
                
                break
        
        if not posts_found:
            print("❌ No posts found with any selector. Let's try extracting all text content...")
            # Fallback: extract all visible text
            all_text = await page.evaluate('document.body.innerText')
            print("📝 Page content preview:")
            print(all_text[:500] + "..." if len(all_text) > 500 else all_text)
    
    async def extract_single_post_data(self, post_element, index):
        """
        Extract data from a single post element
        """
        try:
            # Try to extract common post data fields
            post_data = {
                'index': index,
                'post_url': '',
                'platform': '',
                'caption': '',
                'date': '',
                'creator_name': '',
                'creator_handle': '',
                'impressions': 0,
                'engagements': 0,
                'likes': 0,
                'comments': 0,
                'shares': 0,
                'raw_html': ''
            }
            
            # Get the raw HTML for debugging
            post_data['raw_html'] = await post_element.inner_html()
            
            # Try to extract text content
            text_content = await post_element.inner_text()
            post_data['raw_text'] = text_content
            
            # Try to find links (post URLs)
            links = await post_element.locator('a[href*="instagram.com"], a[href*="tiktok.com"], a[href*="youtube.com"], a[href*="facebook.com"]').all()
            if links:
                post_data['post_url'] = await links[0].get_attribute('href')
                
                # Determine platform from URL
                url = post_data['post_url'].lower()
                if 'instagram' in url:
                    post_data['platform'] = 'Instagram'
                elif 'tiktok' in url:
                    post_data['platform'] = 'TikTok'
                elif 'youtube' in url:
                    post_data['platform'] = 'YouTube'
                elif 'facebook' in url:
                    post_data['platform'] = 'Facebook'
            
            # Try to extract numbers (metrics)
            numbers = []
            import re
            number_matches = re.findall(r'[\d,]+', text_content)
            for match in number_matches:
                try:
                    num = int(match.replace(',', ''))
                    numbers.append(num)
                except:
                    continue
            
            # Assign numbers to metrics (largest numbers are usually impressions/views)
            if numbers:
                numbers.sort(reverse=True)
                if len(numbers) >= 1:
                    post_data['impressions'] = numbers[0]
                if len(numbers) >= 2:
                    post_data['engagements'] = numbers[1]
                if len(numbers) >= 3:
                    post_data['likes'] = numbers[2]
            
            return post_data
            
        except Exception as e:
            print(f"⚠️ Error extracting post data: {e}")
            return None
    
    def save_to_csv(self, filename="creatoriq_posts_extracted.csv"):
        """
        Save extracted posts to CSV file
        """
        if not self.posts_data:
            print("❌ No posts to save")
            return
            
        output_file = Path("data") / filename
        output_file.parent.mkdir(exist_ok=True)
        
        # Define CSV columns
        columns = [
            'index', 'post_url', 'platform', 'creator_name', 'creator_handle',
            'caption', 'date', 'impressions', 'engagements', 'likes', 
            'comments', 'shares', 'raw_text'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            
            for post in self.posts_data:
                # Only write the columns we want (exclude raw_html)
                row = {col: post.get(col, '') for col in columns}
                writer.writerow(row)
        
        print(f"💾 Saved {len(self.posts_data)} posts to: {output_file}")
        
        # Print summary
        platforms = {}
        total_impressions = 0
        total_engagements = 0
        
        for post in self.posts_data:
            platform = post.get('platform', 'Unknown')
            platforms[platform] = platforms.get(platform, 0) + 1
            total_impressions += post.get('impressions', 0)
            total_engagements += post.get('engagements', 0)
        
        print("\n📊 EXTRACTION SUMMARY:")
        print(f"Total Posts: {len(self.posts_data)}")
        print(f"Total Impressions: {total_impressions:,}")
        print(f"Total Engagements: {total_engagements:,}")
        print("Platform Breakdown:")
        for platform, count in platforms.items():
            percentage = (count / len(self.posts_data)) * 100
            print(f"  {platform}: {count} posts ({percentage:.1f}%)")

async def main():
    """
    Main function to run the extractor
    """
    # Default CreatorIQ report URL - replace with your actual URL
    report_url = "https://report.driveshop.com/report/audi_media_spotl-dcMIG3Mp5APt/posts"
    
    print("🚀 CreatorIQ Browser Data Extractor")
    print("=" * 50)
    print(f"Target URL: {report_url}")
    print()
    
    extractor = CreatorIQBrowserExtractor(report_url)
    
    # Extract all posts
    posts = await extractor.extract_all_posts()
    
    if posts:
        # Save to CSV
        extractor.save_to_csv()
        print("\n🎉 Extraction completed successfully!")
    else:
        print("\n❌ No posts were extracted. Check the URL and page structure.")

if __name__ == "__main__":
    asyncio.run(main()) 