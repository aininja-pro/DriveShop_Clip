import re
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
import logging

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

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
    
    # Step 1: Try basic extraction (site-specific or generic)
    basic_extracted = _extract_with_basic_methods(soup, url)
    
    # Step 2: Quality check
    if not is_content_quality_poor(basic_extracted, url, expected_topic):
        # Basic extraction succeeded
        log_content_excerpt(basic_extracted, "Basic")
        return basic_extracted
    
    # Step 3: Basic extraction failed quality check - try alternatives
    logger.info(f"Basic extraction failed quality check ({len(basic_extracted)} chars), trying alternatives")
    
    alternative_extracted = try_alternative_extraction(html, url, expected_topic)
    
    if alternative_extracted and not is_content_quality_poor(alternative_extracted, url, expected_topic):
        # Alternative extraction succeeded
        log_content_excerpt(alternative_extracted, "Alternative")
        return alternative_extracted
    
    # Step 4: All methods failed - return the best we have
    if len(alternative_extracted) > len(basic_extracted):
        logger.warning("All extractions failed quality check, returning best alternative result")
        log_content_excerpt(alternative_extracted, "Fallback Alternative")
        return alternative_extracted
    else:
        logger.warning("All extractions failed quality check, returning basic result")
        log_content_excerpt(basic_extracted, "Fallback Basic")
        return basic_extracted

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
    
    # If no container found, try to extract from body
    if not content_container:
        logger.warning("No content container found, extracting from body")
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
    if not extracted_content or len(extracted_content.strip()) < 200:
        return True
    
    content_lower = extracted_content.lower()
    
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