"""
Debug helper to analyze YouTube HTML structure for date extraction
"""

import re
from bs4 import BeautifulSoup

def analyze_youtube_html_for_dates(html_content: str, max_videos: int = 5):
    """
    Analyze YouTube HTML to understand where dates are located
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    print("=== YouTube HTML Date Analysis ===\n")
    
    # Find all video title elements
    video_titles = soup.find_all(id="video-title")
    print(f"Found {len(video_titles)} videos\n")
    
    # Analyze first few videos
    for i, title_elem in enumerate(video_titles[:max_videos]):
        print(f"Video {i+1}: {title_elem.get_text(strip=True)[:60]}...")
        
        # Check different levels of parent hierarchy
        current = title_elem
        for level in range(5):  # Check up to 5 levels up
            current = current.parent if current else None
            if not current:
                break
                
            # Look for date patterns in this level
            date_pattern = re.compile(r'\d+\s*(second|minute|hour|day|week|month|year)s?\s*ago', re.I)
            
            # Check text content
            text_matches = current.find_all(string=date_pattern)
            if text_matches:
                print(f"  Level {level}: Found date text: '{text_matches[0].strip()}'")
            
            # Check aria-labels
            aria_elements = current.find_all(attrs={'aria-label': date_pattern})
            for elem in aria_elements:
                print(f"  Level {level}: Found in aria-label: '{elem.get('aria-label')}'")
            
            # Check specific classes
            for class_name in ['inline-metadata-item', 'metadata-line', 'video-metadata', 'style-scope ytd-video-meta-block']:
                elements = current.find_all(class_=class_name)
                for elem in elements:
                    elem_text = elem.get_text(strip=True)
                    if date_pattern.search(elem_text):
                        print(f"  Level {level}: Found in class '{class_name}': '{elem_text}'")
        
        print()

if __name__ == "__main__":
    # Test with a small sample
    sample = """
    <div id="video-title">Test Video</div>
    <div class="metadata-line">
        <span class="inline-metadata-item">2 days ago</span>
    </div>
    """
    
    analyze_youtube_html_for_dates(sample)