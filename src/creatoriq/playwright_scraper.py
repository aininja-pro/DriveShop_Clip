import asyncio
import json
import os
from playwright.async_api import async_playwright
from src.utils.logger import setup_logger

# Use the existing DriveShop logger system
logger = setup_logger(__name__)

async def scrape_creatoriq(url: str, scrolls: int = 20, scroll_pause: float = 2.0) -> tuple:
    """
    Scrape CreatorIQ with full network capture (no filtering).
    
    Returns:
        tuple: (html_content, captured_api_responses)
    """
    logger.info(f"🎬 Starting CreatorIQ scrape with FULL NETWORK CAPTURE for: {url}")
    logger.info(f"📜 Configured for {scrolls} scrolls with {scroll_pause}s pause between scrolls")
    
    # Storage for captured API responses
    captured_responses = []
    request_count = 0
    json_file_count = 0
    
    # Create network dumps directory
    network_dumps_dir = "data/network_dumps"
    os.makedirs(network_dumps_dir, exist_ok=True)
    logger.info(f"📁 Created network dumps directory: {network_dumps_dir}")
    
    async def handle_response(response):
        """Capture ALL network responses with full logging."""
        nonlocal request_count, json_file_count
        request_count += 1
        
        try:
            url_str = response.url
            status = response.status
            content_type = response.headers.get("content-type", "")
            
            # Log EVERY request
            logger.info(f"📡 Request #{request_count}: {url_str}")
            logger.info(f"   Status: {status} | Content-Type: {content_type}")
            
            # If it's JSON, save it to disk for analysis
            if "application/json" in content_type.lower():
                try:
                    json_data = await response.json()
                    response_size = len(str(json_data))
                    logger.info(f"   📄 JSON Response Size: {response_size:,} chars")
                    
                    # Generate filename from URL
                    filename = url_str.split("?")[0].split("/")[-1] or "unknown"
                    if not filename or filename == "unknown":
                        filename = f"response_{request_count}"
                    
                    # Add timestamp to avoid conflicts
                    json_file_count += 1
                    filepath = os.path.join(network_dumps_dir, f"{json_file_count:03d}_{filename}.json")
                    
                    # Save JSON to disk
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"   💾 Saved JSON to: {filepath}")
                    
                    # Store the response data for processing
                    captured_responses.append({
                        'url': url_str,
                        'status': status,
                        'content_type': content_type,
                        'data': json_data,
                        'size': response_size,
                        'file_path': filepath
                    })
                    
                    # Log if this looks like a large response (potential post data)
                    if response_size > 10000:  # 10KB+
                        logger.info(f"   🎯 LARGE JSON RESPONSE DETECTED! ({response_size:,} chars) - Potential post data!")
                    
                except Exception as e:
                    logger.warning(f"   ❌ Failed to parse JSON from {url_str}: {e}")
            else:
                # Log non-JSON responses too
                try:
                    content_length = len(await response.body())
                    logger.info(f"   📄 Non-JSON Response Size: {content_length:,} bytes")
                except:
                    logger.info(f"   📄 Non-JSON Response (size unknown)")
            
        except Exception as e:
            logger.warning(f"❌ Error handling response #{request_count}: {e}")
    
    async with async_playwright() as p:
        logger.info("🚀 Launching Chromium browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36")
        
        # 🔍 FULL NETWORK CAPTURE: Set up response listener (NO FILTERING)
        logger.info("🔍 Setting up FULL network interception (no filtering)...")
        page.on("response", handle_response)
        
        logger.info(f"🌐 Navigating to: {url}")
        await page.goto(url, wait_until='networkidle')
        logger.info("✅ Page loaded successfully")
        logger.info(f"📊 Requests captured during page load: {request_count}")

        logger.info(f"🔄 Starting infinite scroll process ({scrolls} scrolls)...")
        logger.info("📡 Full network capture active - logging ALL requests...")
        
        for i in range(scrolls):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await asyncio.sleep(scroll_pause)
            
            # Log progress every 5 scrolls
            if (i + 1) % 5 == 0:
                logger.info(f"📜 Completed {i + 1}/{scrolls} scrolls | Total requests: {request_count} | JSON files: {json_file_count}")
        
        logger.info("⏳ Waiting for final content to load...")
        await page.wait_for_load_state("networkidle")
        
        logger.info("📄 Extracting page content...")
        content = await page.content()
        
        logger.info("🔒 Closing browser...")
        await browser.close()
        
        logger.info(f"✅ Full network capture complete!")
        logger.info(f"   📄 HTML content: {len(content):,} characters")
        logger.info(f"   📡 Total network requests: {request_count}")
        logger.info(f"   📄 JSON responses saved: {json_file_count}")
        
        # Log summary of all captured responses
        if captured_responses:
            logger.info("📋 JSON responses summary:")
            for i, resp in enumerate(captured_responses, 1):
                size_indicator = "🎯 LARGE" if resp['size'] > 10000 else "📄 small"
                logger.info(f"   {i}. {size_indicator} ({resp['size']:,} chars) - {resp['url']}")
                logger.info(f"      💾 File: {resp['file_path']}")
        
        # Identify potential post data responses
        large_responses = [r for r in captured_responses if r['size'] > 10000]
        if large_responses:
            logger.info(f"🎯 POTENTIAL POST DATA RESPONSES ({len(large_responses)} found):")
            for resp in large_responses:
                logger.info(f"   🎯 {resp['url']} ({resp['size']:,} chars)")
                logger.info(f"      💾 Analyze file: {resp['file_path']}")
        
        return content, captured_responses

def get_creatoriq_html(url: str, scrolls: int = 20) -> str:
    """
    Legacy function for backward compatibility.
    Returns only HTML content.
    """
    logger.info(f"🎯 CreatorIQ scraper called with URL: {url}")
    html_content, _ = asyncio.run(scrape_creatoriq(url, scrolls))
    return html_content

def get_creatoriq_data(url: str, scrolls: int = 20) -> tuple:
    """
    New function that returns both HTML and captured API responses.
    
    Returns:
        tuple: (html_content, api_responses)
    """
    logger.info(f"🎯 CreatorIQ scraper with FULL NETWORK CAPTURE called: {url}")
    return asyncio.run(scrape_creatoriq(url, scrolls))

async def scrape_full_network_debug(url: str):
    """
    Standalone debug function for full network analysis.
    Use this for pure network mapping without other processing.
    """
    logger.info(f"🔬 DEBUG: Full network capture for: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        network_dumps_dir = "data/network_dumps_debug"
        os.makedirs(network_dumps_dir, exist_ok=True)
        logger.info(f"📁 Debug network dumps directory: {network_dumps_dir}")

        request_count = 0

        async def handle_response(response):
            nonlocal request_count
            request_count += 1
            
            url_str = response.url
            status = response.status
            content_type = response.headers.get("content-type", "")
            
            print(f"Captured: {url_str} [Status: {status}] [Content-Type: {content_type}]")

            if "application/json" in content_type:
                try:
                    json_data = await response.json()
                    filename = url_str.split("?")[0].split("/")[-1] or "unknown"
                    filepath = os.path.join(network_dumps_dir, f"{request_count:03d}_{filename}.json")
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, indent=2)
                    print(f"  → Saved JSON: {filepath} ({len(str(json_data)):,} chars)")
                except Exception as e:
                    print(f"  → Failed to parse JSON: {e}")

        page.on("response", handle_response)

        await page.goto(url)
        
        for i in range(20):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            print(f"Scroll {i+1}/20 - Total requests: {request_count}")

        await page.wait_for_load_state("networkidle")
        await browser.close()
        
        print(f"🎯 Network capture complete! Total requests: {request_count}")
        print(f"📁 Check files in: {network_dumps_dir}")

def debug_network_capture(url: str):
    """Helper function to run debug network capture."""
    return asyncio.run(scrape_full_network_debug(url)) 