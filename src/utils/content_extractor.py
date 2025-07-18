import re
import json
import requests
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
import logging
from urllib.parse import urlparse, urljoin

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def extract_fliphtml5(html: str) -> Optional[str]:
    """
    Extract plain text content from FlipHTML5 viewer if present.
    
    Args:
        html: Raw HTML content from the page
        
    Returns:
        Plain text content if FlipHTML5 viewer detected, None otherwise
    """
    logger.info("Checking for FlipHTML5 viewer...")
    
    # DEBUG: Log HTML snippet to see what we're working with
    logger.info(f"HTML content length: {len(html)} characters")
    logger.info(f"HTML preview (first 500 chars): {html[:500]}")
    
    # Updated detection: Look for FlipHTML5 navigation controls (rendered content)
    fliphtml5_indicators = [
        "First Previous Page Next Page Last",
        "Return Home Zoom In Search Thumbnails Auto Flip",
        "Sound Off Social Share Fullscreen Email",
        "fliphtml5",
        "Auto Flip Sound Off"
    ]
    
    # Check if this looks like FlipHTML5 rendered content
    is_fliphtml5 = any(indicator in html for indicator in fliphtml5_indicators)
    
    if is_fliphtml5:
        logger.info("🎯 FlipHTML5 viewer detected via navigation controls!")
        
        # Try to find the flipbook URL in the original HTML (before rendering)
        # Look for common FlipHTML5 URL patterns
        flipbook_patterns = [
            r'src="(https://online\.fliphtml5\.com/[^/]+/[^/]+/)"',
            r'href="(https://online\.fliphtml5\.com/[^/]+/[^/]+/[^"]*)"',
            r'"(https://online\.fliphtml5\.com/[^"]+)"'
        ]
        
        flipbook_url = None
        for pattern in flipbook_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                flipbook_url = match.group(1)
                if not flipbook_url.endswith('/'):
                    flipbook_url += '/'
                logger.info(f"Found flipbook URL: {flipbook_url}")
                break
        
        if flipbook_url:
            # Try method 1: Look for text version link
            text_url = flipbook_url + "text/index.html"
            logger.info(f"Trying text version URL: {text_url}")
            
            try:
                response = requests.get(text_url, timeout=20)
                if response.status_code == 200:
                    text_soup = BeautifulSoup(response.text, "lxml")
                    text_content = text_soup.get_text(" ", strip=True)
                    if len(text_content) > 100:  # Ensure we got substantial content
                        logger.info(f"✅ Successfully extracted {len(text_content)} chars from text version")
                        return text_content
                    else:
                        logger.warning("Text version URL returned minimal content")
                else:
                    logger.warning(f"Text version URL returned status {response.status_code}")
            except Exception as e:
                logger.warning(f"Failed to fetch text version: {e}")
            
            # Try method 2: JSON endpoint
            json_url = flipbook_url + "text/text.json"
            logger.info(f"Trying JSON endpoint: {json_url}")
            
            try:
                response = requests.get(json_url, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if "page_text" in data:
                        text_content = " ".join(p.get("text", "") for p in data["page_text"])
                        if len(text_content) > 100:
                            logger.info(f"✅ Successfully extracted {len(text_content)} chars from JSON endpoint")
                            return text_content
                        else:
                            logger.warning("JSON endpoint returned minimal content")
                    else:
                        logger.warning("JSON response missing page_text field")
                else:
                    logger.warning(f"JSON endpoint returned status {response.status_code}")
            except Exception as e:
                logger.warning(f"Failed to fetch JSON endpoint: {e}")
        
        else:
            logger.warning("FlipHTML5 detected but couldn't find flipbook URL")
        
        # ENHANCED: If we can't find the text endpoints, try more aggressive content extraction
        logger.info("Trying enhanced text extraction from rendered FlipHTML5...")
        soup = BeautifulSoup(html, 'lxml')
        
        # Try to extract from page text spans or divs that might contain article content
        article_selectors = [
            'div[class*="page-text"]',
            'span[class*="page-text"]', 
            'div[class*="article"]',
            'div[class*="content"]',
            'div[class*="text"]',
            '.page-content',
            '.article-content',
            '.text-content',
            # More aggressive selectors for FlipHTML5 content
            'div[style*="position: absolute"]',  # FlipHTML5 often uses positioned divs
            'span[style*="position: absolute"]',
            'div p',  # Any paragraphs in divs
            'p'       # All paragraphs as fallback
        ]
        
        extracted_content = ""
        article_paragraphs = []
        
        # Try each selector and collect substantial text
        for selector in article_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(" ", strip=True)
                
                # Skip navigation controls and very short text
                if len(text) < 30:
                    continue
                    
                # Skip if it's navigation controls
                is_navigation = any(indicator.lower() in text.lower() for indicator in fliphtml5_indicators)
                if is_navigation:
                    continue
                
                # Look for automotive content indicators
                automotive_keywords = ['vehicle', 'car', 'sedan', 'suv', 'mpg', 'horsepower', 'engine', 'review', 'drive', 'performance']
                has_automotive_content = any(keyword in text.lower() for keyword in automotive_keywords)
                
                # Include text that's substantial and potentially automotive-related
                if has_automotive_content or len(text) > 100:
                    article_paragraphs.append(text)
        
        # Combine unique paragraphs
        unique_paragraphs = []
        for para in article_paragraphs:
            # Avoid duplicates
            if not any(para[:50] in existing[:50] for existing in unique_paragraphs):
                unique_paragraphs.append(para)
        
        extracted_content = "\n\n".join(unique_paragraphs)
        
        if extracted_content and len(extracted_content.strip()) > 200:
            logger.info(f"✅ Extracted {len(extracted_content)} chars from FlipHTML5 enhanced selectors")
            return extracted_content.strip()
        
        # If specific selectors don't work, try title-based extraction
        # Look for the article title and try to find content near it
        title_patterns = [
            r'(20\d{2})\s+([A-Z][a-z]+\s+[A-Z0-9-]+)',  # "2025 Genesis G80"
            r'([A-Z][a-z]+\s+[A-Z][A-Z0-9-]+)',         # "Genesis G80"
            r'(\w+\s+CX-\d+)',                           # "Mazda CX-90"
        ]
        
        page_text = soup.get_text()
        for pattern in title_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                title = match.group(0)
                logger.info(f"Found potential title: {title}")
                
                # Try to extract content around the title
                title_index = page_text.lower().find(title.lower())
                if title_index >= 0:
                    # Extract a reasonable chunk of content after the title
                    start_pos = max(0, title_index - 100)
                    end_pos = min(len(page_text), title_index + 2000)
                    content_chunk = page_text[start_pos:end_pos]
                    
                    # Clean up navigation text
                    for indicator in fliphtml5_indicators:
                        content_chunk = content_chunk.replace(indicator, "")
                    
                    content_chunk = re.sub(r'\s+', ' ', content_chunk).strip()
                    
                    if len(content_chunk) > 100:
                        logger.info(f"✅ Extracted {len(content_chunk)} chars via title-based extraction")
                        return content_chunk
        
        # Final fallback: Just return the title we can find (better than navigation controls)
        all_text = soup.get_text(" ", strip=True)
        
        # Remove all the navigation controls
        for indicator in fliphtml5_indicators:
            all_text = all_text.replace(indicator, "")
        
        # Remove numbers (page numbers)
        all_text = re.sub(r'\b\d+\s*-?\s*\d+\b', '', all_text)
        all_text = re.sub(r'\s+', ' ', all_text).strip()
        
        # Only return if we have more than just the URL/title
        if len(all_text) > 50:
            logger.info(f"✅ Extracted {len(all_text)} chars via fallback FlipHTML5 cleaning")
            return all_text
        else:
            logger.warning("FlipHTML5 extraction couldn't find substantial content")
            # Return None so other extraction methods can try
            return None
    
    else:
        logger.info("No FlipHTML5 content found")
    
    return None

def extract_article_content(html: str, url: str, expected_topic: str = "") -> str:
    """
    Extract just the main article content from HTML, filtering out scripts, styles, navigation, etc.
    Uses quality-based escalation to try alternative methods if basic extraction fails.
    
    Args:
        html: Full HTML content
        url: URL of the page (used to determine site-specific extraction)
        expected_topic: Expected topic for quality checking (e.g., "VW Jetta")
        
    Returns:
        Extracted article text
    """
    if not html:
        logger.warning("No HTML content provided for extraction")
        return ""
    
    # Initialize BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove all script, style elements and comments
    for element in soup(['script', 'style', 'noscript', 'iframe', 'svg']):
        element.decompose()
        
    # Try to remove navigation, headers, footers
    for nav in soup.find_all(['nav', 'header', 'footer']):
        nav.decompose()
    
    # Try to remove ads and banners
    for ad in soup.find_all(class_=lambda c: c and ('ad' in c.lower() or 'banner' in c.lower() or 'cookie' in c.lower())):
        ad.decompose()
    
    # Step 1: Try site-specific extraction first
    site_specific_content = try_site_specific_extraction(soup, url, expected_topic)
    if site_specific_content:
        # For SpotlightEP, if we got any content from site-specific extraction, use it
        # (site-specific already handles FlipHTML5 detection and quality checks)
        if "spotlightepnews.com" in url and len(site_specific_content) > 200:
            logger.info(f"Using SpotlightEP content ({len(site_specific_content)} chars) - site-specific extraction succeeded")
            log_content_excerpt(site_specific_content, "SpotlightEP-Specific")
            return site_specific_content
        elif not is_content_quality_poor(site_specific_content, url, expected_topic):
            log_content_excerpt(site_specific_content, "Site-Specific")
            return site_specific_content
    
    # Step 2: Try basic extraction (site-specific or generic)
    basic_extracted = _extract_with_basic_methods(soup, url)
    
    # Step 3: Quality check
    if not is_content_quality_poor(basic_extracted, url, expected_topic):
        # Basic extraction succeeded
        log_content_excerpt(basic_extracted, "Basic")
        return basic_extracted
    
    # Step 4: Basic extraction failed quality check - try alternatives
    logger.info(f"Basic extraction failed quality check ({len(basic_extracted)} chars), trying alternatives")
    
    alternative_extracted = try_alternative_extraction(html, url, expected_topic)
    
    if alternative_extracted and not is_content_quality_poor(alternative_extracted, url, expected_topic):
        # Alternative extraction succeeded
        log_content_excerpt(alternative_extracted, "Alternative")
        return alternative_extracted
    
    # Step 5: All methods failed - return the best we have
    if len(alternative_extracted) > len(basic_extracted):
        logger.warning("All extractions failed quality check, returning best alternative result")
        log_content_excerpt(alternative_extracted, "Fallback Alternative")
        return alternative_extracted
    else:
        logger.warning("All extractions failed quality check, returning basic result")
        log_content_excerpt(basic_extracted, "Fallback Basic")
        return basic_extracted

def try_site_specific_extraction(soup: BeautifulSoup, url: str, expected_topic: str = "") -> str:
    """
    Try site-specific extraction methods for known problematic sites.
    
    Args:
        soup: BeautifulSoup object with cleaned HTML
        url: URL of the page
        expected_topic: Expected topic (e.g., "VW Jetta")
        
    Returns:
        Extracted content using site-specific methods, or empty string if not applicable
    """
    domain = urlparse(url).netloc.lower()
    
    # Handle thegentlemanracer.com specifically
    if 'thegentlemanracer.com' in domain:
        return extract_thegentlemanracer_content(soup, url, expected_topic)
    
    # Handle spotlightepnews.com specifically (PDF viewer/flipbook format)
    if 'spotlightepnews.com' in domain:
        return extract_spotlightepnews_content(soup, url, expected_topic)
    
    # Add other site-specific handlers here as needed
    # if 'anothersite.com' in domain:
    #     return extract_anothersite_content(soup, url, expected_topic)
    
    return ""

def extract_thegentlemanracer_content(soup: BeautifulSoup, url: str, expected_topic: str = "") -> str:
    """
    Site-specific extraction for thegentlemanracer.com.
    This site has sidebar content with other vehicle reviews that can confuse the generic extractor.
    """
    logger.info("Using thegentlemanracer.com-specific content extraction")
    
    article_text = ""
    
    # Try to find the main article content area
    # Look for the post content container
    content_selectors = [
        '.post-content',
        '.entry-content', 
        'article .content',
        '.single-post-content',
        'div[class*="post-content"]',
        'div[class*="entry-content"]'
    ]
    
    content_container = None
    for selector in content_selectors:
        elements = soup.select(selector)
        if elements:
            content_container = elements[0]  # Take the first match
            logger.info(f"Found thegentlemanracer content using selector: {selector}")
            break
    
    # If no specific content container found, try to find the main article
    if not content_container:
        article_element = soup.find('article')
        if article_element:
            content_container = article_element
            logger.info("Using article element for thegentlemanracer content")
    
    # If still nothing, try finding a div that contains the title and substantial content
    if not content_container:
        title_element = soup.find('h1')
        if title_element:
            # Look for the parent container that has the most paragraphs
            current = title_element
            best_container = None
            max_paragraphs = 0
            
            for _ in range(5):  # Go up max 5 levels
                current = current.parent if current else None
                if not current:
                    break
                    
                paragraphs = current.find_all('p')
                if len(paragraphs) > max_paragraphs:
                    max_paragraphs = len(paragraphs)
                    best_container = current
            
            if best_container and max_paragraphs >= 3:
                content_container = best_container
                logger.info(f"Found thegentlemanracer content by title proximity ({max_paragraphs} paragraphs)")
    
    if not content_container:
        logger.warning("Could not find specific content container for thegentlemanracer.com")
        return ""
    
    # Remove any sidebar elements that might be within the container
    sidebar_selectors = [
        '.sidebar',
        '.widget',
        '.related-posts',
        '.recent-posts',
        '.popular-posts',
        'aside',
        '[class*="sidebar"]',
        '[class*="widget"]',
        '[class*="related"]'
    ]
    
    for selector in sidebar_selectors:
        for element in content_container.select(selector):
            element.decompose()
    
    # Extract the title
    title = soup.find('h1')
    if title:
        title_text = title.get_text().strip()
        article_text += title_text + "\n\n"
        logger.debug(f"Extracted title: {title_text[:100]}...")
    
    # Extract paragraphs from the content container
    paragraphs = content_container.find_all('p')
    paragraph_count = 0
    
    for p in paragraphs:
        text = p.get_text().strip()
        if len(text) > 30:  # Skip very short paragraphs
            # Skip paragraphs that look like navigation or sidebar content
            text_lower = text.lower()
            if any(skip_phrase in text_lower for skip_phrase in [
                'related posts', 'recent posts', 'you may also like', 'more from',
                'categories:', 'tags:', 'share this', 'follow us', 'subscribe'
            ]):
                continue
                
            article_text += text + "\n\n"
            paragraph_count += 1
    
    # Clean up the text
    article_text = clean_text(article_text)
    
    logger.info(f"Extracted {paragraph_count} paragraphs from thegentlemanracer.com ({len(article_text)} chars)")
    
    # Final validation - make sure this looks like actual article content
    if len(article_text) < 500:
        logger.warning("thegentlemanracer extraction resulted in very short content")
        return ""
    
    # If we have an expected topic, do a basic relevance check
    if expected_topic:
        topic_words = expected_topic.lower().split()
        article_lower = article_text.lower()
        matches = sum(1 for word in topic_words if word in article_lower)
        
        if matches == 0:
            logger.warning(f"thegentlemanracer extraction doesn't mention expected topic: {expected_topic}")
            return ""
        else:
            logger.info(f"thegentlemanracer extraction mentions {matches}/{len(topic_words)} topic words")
    
    return article_text

def extract_spotlightepnews_content(soup: BeautifulSoup, url: str, expected_topic: str = "") -> str:
    """
    Site-specific extraction for spotlightepnews.com.
    This site uses FlipHTML5 viewer that requires special handling.
    """
    logger.info("Using spotlightepnews.com-specific content extraction")
    
    # FIRST: Check if this is a category/index page - extract article links instead of returning empty
    if '/category/' in url or url.endswith('/automotive/') or url.endswith('/automotive'):
        logger.info("🔍 Detected category page - extracting article links from ScrapingBee content")
        return extract_article_links_from_category(soup, url, expected_topic)
    
    # SECOND: Try FlipHTML5 extraction if this is a flipbook article
    original_html = str(soup)  # Get the full HTML for FlipHTML5 detection
    fliphtml5_content = extract_fliphtml5(original_html)
    if fliphtml5_content and len(fliphtml5_content) > 200:  # Require substantial content
        logger.info(f"✅ FlipHTML5 extraction successful: {len(fliphtml5_content)} characters")
        return fliphtml5_content  # Return immediately, don't continue to generic extraction
    elif fliphtml5_content:
        logger.warning(f"FlipHTML5 extracted only {len(fliphtml5_content)} chars - trying enhanced extraction")
    
    # FALLBACK: Use existing extraction methods for non-flipbook content
    logger.info("No FlipHTML5 content found, trying standard spotlightepnews extraction")
    
    article_text = ""
    
    # Look for specific content containers that work better than generic extraction
    content_selectors = [
        # Try article text containers first
        'div[class*="content"] p',
        'div[class*="article"] p', 
        'div[class*="post"] p',
        'section[class*="content"] p',
        'main p',
        # Fallback to any substantial paragraph content
        'div p',
        'p'
    ]
    
    for selector in content_selectors:
        try:
            elements = soup.select(selector)
            candidate_paragraphs = []
            
            for element in elements:
                text = element.get_text(strip=True)
                
                # Skip short text and navigation elements
                if len(text) < 50:
                    continue
                    
                # Skip obvious navigation content
                nav_indicators = ['firstprevious', 'nextpage', 'autoflip', 'fullscreen', 'thumbnails', 'zoom in', 'social share']
                if any(nav in text.lower() for nav in nav_indicators):
                    continue
                
                # Look for article content indicators
                content_indicators = ['genesis', 'g80', 'sedan', 'luxury', 'vehicle', 'car', 'auto', 'review', 'christopher', 'randazzo']
                if expected_topic:
                    content_indicators.extend(expected_topic.lower().split())
                    
                if any(indicator in text.lower() for indicator in content_indicators):
                    candidate_paragraphs.append(text)
            
            if candidate_paragraphs:
                article_text = '\n\n'.join(candidate_paragraphs)
                logger.info(f"Found content using selector '{selector}': {len(article_text)} characters")
                break
                
        except Exception as e:
            logger.debug(f"Selector '{selector}' failed: {e}")
            continue
    
    # Final fallback: look for any substantial text blocks
    if not article_text:
        logger.info("No content container found, searching for text blocks with vehicle mentions")
        all_text = soup.get_text(separator=' ', strip=True)
        
        # Look for paragraphs that mention vehicles or automotive content
        paragraphs = [p.strip() for p in all_text.split('\n') if len(p.strip()) > 100]
        vehicle_paragraphs = []
        
        for para in paragraphs:
            # Skip navigation content
            if any(nav in para.lower() for nav in ['firstprevious', 'nextpage', 'autoflip', 'fullscreen']):
                continue
                
            # Include paragraphs with automotive keywords
            if any(keyword in para.lower() for keyword in ['vehicle', 'car', 'sedan', 'suv', 'mpg', 'horsepower', 'engine']):
                vehicle_paragraphs.append(para)
        
        if vehicle_paragraphs:
            article_text = '\n\n'.join(vehicle_paragraphs)
            logger.info(f"Found automotive content via text search: {len(article_text)} characters")
    
    if not article_text:
        logger.info("No specific container found, attempting full-page text extraction")
        # Last resort: get all text and hope for the best
        article_text = soup.get_text(separator=' ', strip=True)
        if article_text:
            article_text = re.sub(r'\s+', ' ', article_text).strip()
    
    if article_text:
        logger.info(f"Successfully extracted {len(article_text)} characters for spotlightepnews.com")
        return article_text
    else:
        logger.warning("Could not find content container for spotlightepnews.com")
        return ""

def _extract_with_basic_methods(soup: BeautifulSoup, url: str) -> str:
    """
    Extract content using basic methods (generic extraction).
    Quality-based escalation will handle cases where basic extraction fails.
    
    Args:
        soup: BeautifulSoup object with cleaned HTML
        url: URL of the page
        
    Returns:
        Extracted content using basic methods
    """
    # Use generic extraction for all sites
    # Quality-based escalation will handle sites where this fails
    return extract_generic_content(soup, url)

def extract_generic_content(soup: BeautifulSoup, url: str) -> str:
    """Generic content extraction for any website."""
    logger.info("Using generic content extraction")
    
    article_text = ""
    
    # Try common article containers
    selectors = [
        'article',
        'main',
        'div.article',
        'div.post',
        'div.entry',
        'div.content',
        'div[itemprop="articleBody"]',
        'div.article-content',
        '.post-content',
        '.entry-content'
    ]
    
    # Look for a container with the main content
    content_container = None
    for selector in selectors:
        elements = soup.select(selector)
        if elements:
            # Pick the largest container by text length as likely main content
            content_container = max(elements, key=lambda e: len(e.get_text(strip=True)))
            logger.info(f"Found content using selector: {selector}")
            break
    
    # ENHANCED: If no container found, use smart content detection instead of body fallback
    if not content_container:
        logger.info("Standard selectors failed, using smart content detection")
        content_container = find_main_content_area(soup)
        
    # If smart detection also failed, fall back to body (but this should be rare now)
    if not content_container:
        logger.warning("Smart content detection failed, extracting from body")
        content_container = soup.body if soup.body else soup
    
    # Extract the title if possible
    title = soup.find('h1')
    if title:
        article_text += title.get_text().strip() + "\n\n"
    
    # Extract paragraphs
    paragraphs = content_container.find_all('p')
    for p in paragraphs:
        text = p.get_text().strip()
        if text and len(text) > 20:  # Skip very short paragraphs
            article_text += text + "\n\n"
    
    # If we couldn't find paragraphs, try to get text from divs
    if not article_text:
        # Find all divs with substantial text
        text_divs = [div for div in content_container.find_all('div') if len(div.get_text(strip=True)) > 100]
        
        # Sort by length (longest first) and take top results
        text_divs.sort(key=lambda div: len(div.get_text(strip=True)), reverse=True)
        
        for div in text_divs[:5]:  # Take top 5 longest text divs
            article_text += div.get_text(strip=True) + "\n\n"
    
    # Clean up the text
    article_text = clean_text(article_text)
    
    # Log excerpt for debugging
    log_content_excerpt(article_text, "Generic")
    
    return article_text

def find_main_content_area(soup: BeautifulSoup) -> Optional[Any]:
    """
    Smart detection of main content area when standard selectors fail.
    Uses content analysis to identify the most likely article container.
    """
    logger.info("Running smart content area detection")
    
    # Find the H1 title first - content is usually near it
    h1 = soup.find('h1')
    if not h1:
        logger.warning("No H1 found for content area detection")
        return None
    
    title_text = h1.get_text().strip()
    logger.info(f"Using H1 as anchor: {title_text[:100]}...")
    
    # Strategy 1: Find the container with the most paragraphs near the H1
    candidates = []
    
    # Check H1's parent and grandparent containers
    current = h1
    for level in range(4):  # Go up 4 levels max
        parent = current.parent if current else None
        if not parent or parent.name in ['html', 'body']:
            break
            
        # Score this container based on content quality
        paragraphs = parent.find_all('p')
        if len(paragraphs) >= 3:  # Must have at least 3 paragraphs
            score = calculate_content_score(parent, title_text)
            candidates.append((parent, score, f"parent_level_{level}"))
            logger.debug(f"Candidate at level {level}: {len(paragraphs)} paragraphs, score {score}")
        
        current = parent
    
    # Strategy 2: Look for containers that follow the H1
    sibling = h1
    for _ in range(10):  # Check next 10 siblings
        sibling = sibling.find_next_sibling() if sibling else None
        if not sibling:
            break
            
        if sibling.name in ['div', 'section', 'article']:
            paragraphs = sibling.find_all('p')
            if len(paragraphs) >= 2:
                score = calculate_content_score(sibling, title_text)
                candidates.append((sibling, score, "following_sibling"))
                logger.debug(f"Sibling candidate: {len(paragraphs)} paragraphs, score {score}")
    
    # Strategy 3: Look for the div with the highest paragraph density in the page
    all_divs = soup.find_all('div')
    for div in all_divs:
        paragraphs = div.find_all('p')
        if len(paragraphs) >= 5:  # Higher threshold for global search
            score = calculate_content_score(div, title_text)
            candidates.append((div, score, "high_density"))
    
    # Select the best candidate
    if candidates:
        best_container, best_score, method = max(candidates, key=lambda x: x[1])
        logger.info(f"Selected content container using {method} with score {best_score}")
        return best_container
    
    logger.warning("Smart content detection found no suitable candidates")
    return None

def calculate_content_score(container: Any, title_text: str) -> float:
    """
    Calculate a quality score for a potential content container.
    Higher scores indicate better content areas.
    """
    score = 0.0
    
    # Get all text in the container
    text = container.get_text(strip=True)
    if len(text) < 200:  # Too short to be main content
        return 0.0
    
    # Score based on paragraph count (more paragraphs = likely article)
    paragraphs = container.find_all('p')
    paragraph_score = len(paragraphs) * 2  # 2 points per paragraph
    score += paragraph_score
    
    # Score based on total text length (but cap it)
    length_score = min(len(text) / 500, 10)  # Max 10 points for length
    score += length_score
    
    # Bonus for having the title text in the container
    if title_text.lower() in text.lower():
        score += 5
    
    # Penalty for navigation-like content
    nav_indicators = ['recent posts', 'related articles', 'categories', 'tags', 'share this', 'follow us']
    nav_count = sum(1 for indicator in nav_indicators if indicator in text.lower())
    score -= nav_count * 3  # -3 points per navigation indicator
    
    # Bonus for article-like structure (sentences ending with periods)
    sentence_count = text.count('.')
    if sentence_count > 10:
        score += min(sentence_count / 10, 5)  # Max 5 bonus points
    
    # Penalty if the container has too many links (likely navigation)
    links = container.find_all('a')
    if len(links) > 20:  # Too many links suggests navigation area
        score -= 5
    
    logger.debug(f"Content score breakdown: paragraphs={paragraph_score}, length={length_score}, sentences={sentence_count}, nav_penalty={nav_count*3}")
    
    return max(score, 0.0)  # Don't return negative scores

def extract_article_links_from_category(soup: BeautifulSoup, url: str, expected_topic: str = "") -> str:
    """
    Extract individual article links from a category page and trigger Index Page Discovery.
    This function should return empty content to trigger the enhanced crawler manager's 
    Index Page Discovery process which properly crawls individual articles.
    """
    logger.info(f"🔍 Detected category page - extracting article links from ScrapingBee content")
    logger.info(f"Extracting article links from category page for topic: {expected_topic}")
    
    # **COMPREHENSIVE DEBUG ANALYSIS**
    logger.info("="*80)
    logger.info("🔍 DETAILED PAGE ANALYSIS")
    logger.info("="*80)
    
    # 1. Basic HTML structure analysis
    logger.info(f"📄 HTML size: {len(str(soup))} characters")
    logger.info(f"📄 Page title: {soup.title.get_text() if soup.title else 'No title'}")
    
    # 2. Look for FlipHTML5 structure (common on spotlightepnews.com)
    fliphtml_elements = soup.find_all(['div', 'iframe'], class_=lambda c: c and ('fliphtml' in str(c).lower() or 'flip' in str(c).lower()))
    if fliphtml_elements:
        logger.info(f"📖 Found {len(fliphtml_elements)} FlipHTML5 elements")
        for i, elem in enumerate(fliphtml_elements[:3]):
            logger.info(f"   FlipHTML5 element {i+1}: {elem.name} with class='{elem.get('class', '')}'")
    
    # 3. Comprehensive link analysis
    all_links = soup.find_all('a', href=True)
    logger.info(f"🔗 Found {len(all_links)} total <a> tags")
    
    if len(all_links) == 0:
        logger.error("❌ CRITICAL: No <a> tags found! Page may not be fully loaded.")
        # Show raw HTML structure to debug
        all_divs = soup.find_all('div')
        logger.info(f"📦 Found {len(all_divs)} div elements instead")
        for i, div in enumerate(all_divs[:10]):
            div_class = div.get('class', [])
            div_id = div.get('id', '')
            logger.info(f"   Div {i+1}: class={div_class}, id='{div_id}'")
        
        # Show first 1000 chars of HTML 
        html_preview = str(soup)[:1000]
        logger.info(f"📄 HTML Preview:\n{html_preview}")
        return ""
    
    # 4. Categorize all links for debugging
    youtube_links = []
    internal_links = []
    external_links = []
    category_links = []
    potential_articles = []
    
    for i, link in enumerate(all_links):
        href = link.get('href', '')
        link_text = link.get_text(strip=True)
        parent_element = link.parent.name if link.parent else 'unknown'
        parent_class = ' '.join(link.parent.get('class', [])) if link.parent and link.parent.get('class') else ''
        
        # Show first 50 links with full details
        if i < 50:
            logger.info(f"🔗 Link {i+1}: {href}")
            logger.info(f"   Text: '{link_text[:80]}'")
            logger.info(f"   Parent: <{parent_element} class='{parent_class}'/>")
        
        # Categorize link
        if 'youtube.com' in href or 'youtu.be' in href:
            youtube_links.append((href, link_text))
        elif href.startswith('/') or 'spotlightepnews.com' in href:
            if '/category/' in href:
                category_links.append((href, link_text))
            else:
                internal_links.append((href, link_text))
                
                # Check if this could be an article
                if (len(href) > 10 and 
                    not href.endswith('/') and 
                    '/tag/' not in href and 
                    '/author/' not in href and
                    '/search' not in href and
                    '#' not in href):
                    potential_articles.append((href, link_text))
        elif href.startswith('http'):
            external_links.append((href, link_text))
    
    # 5. Link summary
    logger.info("📊 LINK ANALYSIS SUMMARY:")
    logger.info(f"   🎥 YouTube links: {len(youtube_links)}")
    logger.info(f"   🏠 Internal links: {len(internal_links)}")
    logger.info(f"   🌐 External links: {len(external_links)}")
    logger.info(f"   📁 Category links: {len(category_links)}")
    logger.info(f"   📰 Potential articles: {len(potential_articles)}")
    
    # 6. **DIRECT SEARCH FOR KNOWN ARTICLES**
    logger.info("="*50)
    logger.info("🎯 SEARCHING FOR KNOWN ARTICLES")
    logger.info("="*50)
    
    # Search for the exact Camry and CX-5 articles we know exist
    known_articles = {
        'Toyota Camry Hybrid': [
            '/all-new-2025-toyota-camry-goes-hybrid-fulltime/',
            'toyota', 'camry', 'hybrid', '2025'
        ],
        'Mazda CX-5': [
            '/success-hasnt-spoiled-the-mazda-cx-5/',
            'mazda', 'cx-5', 'success', 'spoiled'
        ]
    }
    
    found_articles = []
    for article_name, search_terms in known_articles.items():
        url_pattern = search_terms[0]  # First term is the URL pattern
        keywords = search_terms[1:]     # Rest are keywords
        
        logger.info(f"🔍 Searching for {article_name}:")
        logger.info(f"   URL pattern: {url_pattern}")
        logger.info(f"   Keywords: {keywords}")
        
        # Search in all links
        for href, link_text in internal_links + potential_articles:
            href_lower = href.lower()
            text_lower = link_text.lower()
            
            # Check URL pattern match
            url_match = url_pattern.lower() in href_lower
            
            # Check keyword matches
            keyword_matches = sum(1 for kw in keywords if kw in href_lower or kw in text_lower)
            
            if url_match or keyword_matches >= 2:
                found_articles.append((article_name, href, link_text, url_match, keyword_matches))
                logger.info(f"   ✅ FOUND! {href}")
                logger.info(f"      Text: '{link_text}'")
                logger.info(f"      URL match: {url_match}, Keyword matches: {keyword_matches}")
    
    # 7. Topic-specific search
    if expected_topic:
        logger.info("="*50)
        logger.info(f"🎯 SEARCHING FOR TOPIC: {expected_topic}")
        logger.info("="*50)
        
        topic_words = expected_topic.lower().split()
        topic_matches = []
        
        for href, link_text in potential_articles:
            href_lower = href.lower()
            text_lower = link_text.lower()
            
            url_matches = sum(1 for word in topic_words if word in href_lower)
            text_matches = sum(1 for word in topic_words if word in text_lower)
            total_matches = url_matches + text_matches
            
            if total_matches > 0:
                topic_matches.append((href, link_text, url_matches, text_matches, total_matches))
                
        # Sort by total matches (best first)
        topic_matches.sort(key=lambda x: x[4], reverse=True)
        
        logger.info(f"🔍 Found {len(topic_matches)} links matching topic '{expected_topic}':")
        for i, (href, text, url_m, text_m, total) in enumerate(topic_matches[:10]):
            logger.info(f"   {i+1}. {href} (URL:{url_m}, Text:{text_m})")
            logger.info(f"      Text: '{text[:60]}'")
    
    # 8. Final summary
    total_potential = len(potential_articles)
    logger.info("="*50)
    logger.info("📋 FINAL SUMMARY")
    logger.info("="*50)
    logger.info(f"✅ Found {len(found_articles)} known articles")
    logger.info(f"📰 Found {total_potential} potential article links")
    logger.info(f"🔗 Total links analyzed: {len(all_links)}")
    
    if found_articles:
        logger.info("🎉 SUCCESS: Found known articles!")
        for article_name, href, text, url_match, kw_matches in found_articles:
            logger.info(f"   {article_name}: {href}")
    elif total_potential > 0:
        logger.info("⚠️ No exact matches, but found potential articles")
    else:
        logger.error("❌ CRITICAL: No article links found at all!")
    
    # Always return empty to trigger Index Page Discovery
    logger.info("🔄 Returning empty content to trigger Index Page Discovery")
    return ""

def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove redundant newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove common ads/cookie text
    text = re.sub(r'(accept all cookies|privacy policy|terms of service|advertisement|subscribe now)', '', text, flags=re.IGNORECASE)
    
    return text.strip()

def log_content_excerpt(content: str, source_type: str) -> None:
    """Log a short excerpt of the extracted content for debugging."""
    if not content:
        logger.warning(f"{source_type} extraction resulted in empty content")
        return
        
    content_length = len(content)
    excerpt = content[:500] + "..." if content_length > 500 else content
    logger.info(f"Extracted {content_length} characters of {source_type} content. Excerpt: \n{excerpt}")

def is_content_quality_poor(extracted_content: str, url: str, expected_topic: str = "") -> bool:
    """
    Detect if extracted content is poor quality (sidebar, navigation, etc.)
    
    Args:
        extracted_content: The extracted text
        url: Source URL for context
        expected_topic: Expected topic (e.g., "VW Jetta")
        
    Returns:
        True if content quality is poor and should be re-extracted
    """
    if not extracted_content or len(extracted_content.strip()) == 0:
        return True
    
    # For FlipHTML5 sites (like spotlightepnews.com), allow shorter content
    # since the extraction from flipbooks might be legitimately shorter
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    min_length = 100 if 'spotlightepnews.com' in domain else 200
    
    if len(extracted_content.strip()) < min_length:
        return True
    
    content_lower = extracted_content.lower()
    
    # Check for FlipHTML5 navigation controls that indicate failed extraction
    fliphtml5_nav_indicators = [
        'firstprevious page', 'nextpagelast', 'return homezoom', 'thumbnailsauto flip',
        'social sharefullscreen', 'emailmoremore'
    ]
    
    # If content is mostly FlipHTML5 navigation controls, it's poor quality
    nav_count = sum(1 for indicator in fliphtml5_nav_indicators if indicator in content_lower.replace(' ', ''))
    if nav_count >= 2:
        return True
    
    # Check for obvious sidebar/navigation content
    sidebar_indicators = [
        'recent posts', 'related posts', 'you may also like', 'more stories',
        'categories:', 'tags:', 'share this:', 'follow us', 'subscribe',
        'advertisement', 'sponsored content', 'continue reading',
        'popular articles', 'trending now', 'recommended for you'
    ]
    
    # If content is dominated by sidebar indicators
    sidebar_count = sum(1 for indicator in sidebar_indicators if indicator in content_lower)
    if sidebar_count >= 2:  # Multiple sidebar indicators suggest non-article content
        return True
    
    # Check if content mentions completely different topics than expected
    if expected_topic:
        topic_words = expected_topic.lower().split()
        topic_mentions = sum(1 for word in topic_words if word in content_lower)
        
        # If expected topic is completely missing, likely wrong content
        if len(topic_words) > 1 and topic_mentions == 0:
            return True
    
    # Check for navigation-heavy content (lots of short lines)
    lines = [line.strip() for line in extracted_content.split('\n') if line.strip()]
    short_lines = sum(1 for line in lines if len(line) < 50)
    
    # If more than 70% of lines are very short, likely navigation/sidebar
    if len(lines) > 5 and short_lines / len(lines) > 0.7:
        return True
    
    return False

def try_alternative_extraction(html: str, url: str, expected_topic: str = "") -> str:
    """
    Try alternative extraction methods when basic extraction fails quality checks.
    
    Args:
        html: Full HTML content
        url: URL of the page
        expected_topic: Expected topic (e.g., "VW Jetta")
        
    Returns:
        Best extracted content found
    """
    logger.info("Trying alternative extraction methods due to poor quality content")
    
    if not html:
        return ""
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove scripts, styles, etc.
    for element in soup(['script', 'style', 'noscript', 'iframe', 'svg']):
        element.decompose()
    
    # Try multiple alternative methods
    extraction_methods = []
    
    # Method 1: Title-based content discovery
    title_based = extract_content_near_title(soup, url, expected_topic)
    if title_based:
        extraction_methods.append(("title_based", title_based))
    
    # Method 2: Paragraph density analysis
    density_based = extract_highest_paragraph_density(soup, url)
    if density_based:
        extraction_methods.append(("density_based", density_based))
    
    # Method 3: Full text with smart filtering
    filtered_text = extract_full_text_with_filtering(soup, url, expected_topic)
    if filtered_text:
        extraction_methods.append(("filtered_text", filtered_text))
    
    # Method 4: Longest meaningful text block
    longest_block = extract_longest_text_block(soup, url)
    if longest_block:
        extraction_methods.append(("longest_block", longest_block))
    
    # Select the best quality result
    best_content = select_best_extraction(extraction_methods, expected_topic)
    
    if best_content:
        logger.info(f"Alternative extraction succeeded: {len(best_content)} characters")
        return best_content
    else:
        logger.warning("All alternative extraction methods failed")
        return ""

def extract_content_near_title(soup: BeautifulSoup, url: str, expected_topic: str = "") -> str:
    """Find content near the article title"""
    logger.debug("Trying title-based content discovery")
    
    # Find the main title (h1)
    title_element = soup.find('h1')
    if not title_element:
        return ""
    
    title_text = title_element.get_text().strip()
    logger.debug(f"Found title: {title_text[:100]}...")
    
    # If we have an expected topic, verify the title is relevant
    if expected_topic:
        topic_words = expected_topic.lower().split()
        title_lower = title_text.lower()
        matches = sum(1 for word in topic_words if word in title_lower)
        if matches == 0:
            logger.debug("Title doesn't match expected topic, skipping")
            return ""
    
    # Find content containers near the title
    content_containers = []
    
    # Look for article content after the title
    current = title_element
    while current:
        current = current.find_next_sibling()
        if current and current.name in ['div', 'section', 'article']:
            text = current.get_text(strip=True)
            if len(text) > 500:  # Substantial content
                content_containers.append(current)
        if len(content_containers) >= 3:  # Don't search too far
            break
    
    # Also look for parent containers that might hold the content
    parent = title_element.parent
    for _ in range(3):  # Go up max 3 levels
        if parent and parent.name in ['article', 'main', 'div']:
            paragraphs = parent.find_all('p')
            if len(paragraphs) >= 3:  # Has substantial paragraph content
                content_containers.append(parent)
                break
        parent = parent.parent if parent else None
    
    # Extract text from the best container
    best_container = None
    max_paragraph_count = 0
    
    for container in content_containers:
        paragraph_count = len(container.find_all('p'))
        if paragraph_count > max_paragraph_count:
            max_paragraph_count = paragraph_count
            best_container = container
    
    if best_container:
        content = title_text + "\n\n"
        paragraphs = best_container.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 20:  # Skip very short paragraphs
                content += text + "\n\n"
        
        return clean_text(content)
    
    return ""

def extract_highest_paragraph_density(soup: BeautifulSoup, url: str) -> str:
    """Find the area with highest paragraph density (likely main article)"""
    logger.debug("Trying paragraph density analysis")
    
    # Find all containers that might hold content
    containers = soup.find_all(['div', 'section', 'article', 'main'])
    
    best_container = None
    best_score = 0
    
    for container in containers:
        paragraphs = container.find_all('p')
        
        if len(paragraphs) < 3:  # Need at least 3 paragraphs
            continue
        
        # Calculate paragraph density score
        total_text_length = sum(len(p.get_text(strip=True)) for p in paragraphs)
        avg_paragraph_length = total_text_length / len(paragraphs) if paragraphs else 0
        
        # Score based on number of paragraphs and average length
        score = len(paragraphs) * min(avg_paragraph_length / 100, 3)  # Cap the length bonus
        
        if score > best_score:
            best_score = score
            best_container = container
    
    if best_container:
        # Extract title if available
        title = soup.find('h1')
        content = ""
        if title:
            content += title.get_text().strip() + "\n\n"
        
        # Extract paragraphs
        paragraphs = best_container.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 20:
                content += text + "\n\n"
        
        return clean_text(content)
    
    return ""

def extract_full_text_with_filtering(soup: BeautifulSoup, url: str, expected_topic: str = "") -> str:
    """Extract all text but filter out navigation/sidebar content"""
    logger.debug("Trying full text extraction with filtering")
    
    # Remove obvious navigation/sidebar elements
    for element in soup.find_all(['nav', 'header', 'footer', 'aside']):
        element.decompose()
    
    # Remove elements with navigation-like classes
    nav_classes = ['nav', 'menu', 'sidebar', 'related', 'recommended', 'recent']
    for class_name in nav_classes:
        for element in soup.find_all(class_=lambda c: c and class_name in c.lower()):
            element.decompose()
    
    # Get title
    title = soup.find('h1')
    content = ""
    if title:
        content += title.get_text().strip() + "\n\n"
    
    # Extract all remaining text but filter by relevance
    all_text = soup.get_text(separator='\n', strip=True)
    lines = [line.strip() for line in all_text.split('\n') if line.strip()]
    
    # Filter lines
    filtered_lines = []
    for line in lines:
        # Skip very short lines (likely navigation)
        if len(line) < 30:
            continue
        
        # Skip obvious navigation text
        if any(nav_word in line.lower() for nav_word in ['recent posts', 'related articles', 'categories', 'tags']):
            continue
        
        # If we have an expected topic, prefer lines that mention it
        if expected_topic:
            topic_words = expected_topic.lower().split()
            if any(word in line.lower() for word in topic_words):
                filtered_lines.append(line)
            elif len(line) > 100:  # Keep long lines even if they don't mention topic
                filtered_lines.append(line)
        else:
            if len(line) > 50:  # Keep substantial lines
                filtered_lines.append(line)
    
    content += '\n\n'.join(filtered_lines[:50])  # Limit to first 50 lines
    return clean_text(content)

def extract_longest_text_block(soup: BeautifulSoup, url: str) -> str:
    """Find the single longest coherent text block"""
    logger.debug("Trying longest text block extraction")
    
    # Find all text-containing elements
    text_elements = soup.find_all(['p', 'div', 'section', 'article'])
    
    longest_element = None
    max_length = 0
    
    for element in text_elements:
        text = element.get_text(strip=True)
        if len(text) > max_length and len(text) > 500:  # Must be substantial
            max_length = len(text)
            longest_element = element
    
    if longest_element:
        # Get title
        title = soup.find('h1')
        content = ""
        if title:
            content += title.get_text().strip() + "\n\n"
        
        # Add the longest text block
        content += longest_element.get_text(strip=True)
        return clean_text(content)
    
    return ""

def select_best_extraction(extraction_methods: list, expected_topic: str = "") -> str:
    """Select the best extraction result from multiple methods"""
    if not extraction_methods:
        return ""
    
    logger.debug(f"Comparing {len(extraction_methods)} extraction results")
    
    best_method = None
    best_score = 0
    
    for method_name, content in extraction_methods:
        if not content or len(content) < 200:
            continue
        
        score = 0
        
        # Length bonus (up to a point)
        score += min(len(content) / 1000, 5)  # Max 5 points for length
        
        # Topic relevance bonus
        if expected_topic:
            topic_words = expected_topic.lower().split()
            content_lower = content.lower()
            topic_mentions = sum(1 for word in topic_words if word in content_lower)
            score += topic_mentions * 2  # 2 points per topic word match
        
        # Quality indicators
        if content.count('.') > 10:  # Has many sentences
            score += 2
        if content.count('\n\n') > 5:  # Has multiple paragraphs
            score += 1
        
        # Penalty for sidebar content
        if is_content_quality_poor(content, "", expected_topic):
            score -= 5
        
        logger.debug(f"Method {method_name}: {len(content)} chars, score: {score:.1f}")
        
        if score > best_score:
            best_score = score
            best_method = (method_name, content)
    
    if best_method:
        method_name, content = best_method
        logger.info(f"Selected best extraction method: {method_name} ({len(content)} chars)")
        return content
    
    return "" 