import re
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
import logging

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def extract_article_content(html: str, url: str) -> str:
    """
    Extract just the main article content from HTML, filtering out scripts, styles, navigation, etc.
    
    Args:
        html: Full HTML content
        url: URL of the page (used to determine site-specific extraction)
        
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
    
    # Site-specific extraction
    if 'motortrend.com' in url:
        return extract_motortrend_content(soup, url)
    elif 'caranddriver.com' in url:
        return extract_caranddriver_content(soup, url)
    else:
        # Generic extraction
        return extract_generic_content(soup, url)

def extract_motortrend_content(soup: BeautifulSoup, url: str) -> str:
    """Extract content specifically from MotorTrend articles."""
    logger.info("Using MotorTrend-specific content extraction")
    
    article_text = ""
    
    # Try multiple possible selectors for MotorTrend
    selectors = [
        'div.article-content',
        'div.contentblock',
        'div.article-body',
        'article',
        'div[itemprop="articleBody"]',
        'main'
    ]
    
    # Look for a container with the main content
    content_container = None
    for selector in selectors:
        container = soup.select_one(selector)
        if container:
            content_container = container
            logger.info(f"Found content using selector: {selector}")
            break
    
    if not content_container:
        logger.warning("Could not find article content with known selectors, falling back to generic extraction")
        return extract_generic_content(soup, url)
    
    # Extract the title if possible
    title = soup.find('h1')
    if title:
        article_text += title.get_text().strip() + "\n\n"
    
    # Extract paragraphs from the content container
    paragraphs = content_container.find_all('p')
    for p in paragraphs:
        text = p.get_text().strip()
        if text and len(text) > 20:  # Skip very short paragraphs (likely not main content)
            article_text += text + "\n\n"
    
    # If no paragraphs found, try to get all text
    if not article_text:
        article_text = content_container.get_text(separator='\n\n', strip=True)
    
    # Clean up the text
    article_text = clean_text(article_text)
    
    # Log excerpt for debugging
    log_content_excerpt(article_text, "MotorTrend")
    
    return article_text

def extract_caranddriver_content(soup: BeautifulSoup, url: str) -> str:
    """Extract content specifically from Car and Driver articles."""
    logger.info("Using Car and Driver-specific content extraction")
    
    article_text = ""
    
    # Try multiple possible selectors for Car and Driver
    selectors = [
        'div.article-body',
        'div.content-body',
        'div.article-container',
        'article',
        'div[itemprop="articleBody"]'
    ]
    
    # Look for a container with the main content
    content_container = None
    for selector in selectors:
        container = soup.select_one(selector)
        if container:
            content_container = container
            logger.info(f"Found content using selector: {selector}")
            break
    
    if not content_container:
        logger.warning("Could not find article content with known selectors, falling back to generic extraction")
        return extract_generic_content(soup, url)
    
    # Extract the title if possible
    title = soup.find('h1')
    if title:
        article_text += title.get_text().strip() + "\n\n"
    
    # Extract paragraphs from the content container
    paragraphs = content_container.find_all('p')
    for p in paragraphs:
        text = p.get_text().strip()
        if text and len(text) > 20:  # Skip very short paragraphs (likely not main content)
            article_text += text + "\n\n"
    
    # If no paragraphs found, try to get all text
    if not article_text:
        article_text = content_container.get_text(separator='\n\n', strip=True)
    
    # Clean up the text
    article_text = clean_text(article_text)
    
    # Log excerpt for debugging
    log_content_excerpt(article_text, "Car and Driver")
    
    return article_text

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