"""
Model variation generator for automotive search.
Handles different formatting patterns for vehicle model names.
"""

import re
from typing import List
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def generate_model_variations(make: str, model: str) -> List[str]:
    """
    Generate comprehensive model name variations to handle different formatting patterns.
    
    Examples:
    - "ES 350" → ["es 350", "es350", "lexus es 350", "lexus es350"]
    - "CX-90" → ["cx-90", "cx 90", "cx90", "mazda cx-90", "mazda cx 90", "mazda cx90"]
    - "3 Series" → ["3 series", "3series", "bmw 3 series", "bmw 3series"]
    
    Args:
        make: Vehicle make (e.g., "Lexus", "Mazda", "BMW")
        model: Vehicle model (e.g., "ES 350", "CX-90", "3 Series")
        
    Returns:
        List of normalized model variations to search for
    """
    make_lower = make.lower()
    model_lower = model.lower()
    
    variations = set()  # Use set to avoid duplicates
    
    # 1. Basic model as-is
    variations.add(model_lower)
    
    # 2. Handle spaces vs no spaces
    model_no_spaces = model_lower.replace(' ', '')
    model_with_spaces = model_lower
    
    variations.add(model_no_spaces)          # "es350", "cx90"
    variations.add(model_with_spaces)        # "es 350", "cx-90"
    
    # 3. Handle hyphens vs spaces vs no separator
    if '-' in model_lower:
        model_hyphen_to_space = model_lower.replace('-', ' ')  # "cx-90" → "cx 90"
        model_hyphen_to_none = model_lower.replace('-', '')    # "cx-90" → "cx90"
        variations.add(model_hyphen_to_space)
        variations.add(model_hyphen_to_none)
    
    if ' ' in model_lower:
        model_space_to_hyphen = model_lower.replace(' ', '-')  # "es 350" → "es-350"
        model_space_to_none = model_lower.replace(' ', '')     # "es 350" → "es350"
        variations.add(model_space_to_hyphen)
        variations.add(model_space_to_none)
    
    # 4. Add make prefix variations
    for var in list(variations):
        variations.add(f"{make_lower} {var}")     # "lexus es350", "mazda cx90"
        variations.add(f"{make_lower}{var}")      # "lexuses350", "mazdacx90"
        if ' ' not in var:  # Only add hyphen for no-space variants
            variations.add(f"{make_lower}-{var}") # "lexus-es350", "mazda-cx90"
    
    # 5. Handle numeric patterns (like "3 Series" vs "3Series")
    # Find patterns like "word number" or "number word"
    number_patterns = [
        (r'(\w+)\s+(\d+)', r'\1\2'),           # "es 350" → "es350"
        (r'(\d+)\s+(\w+)', r'\1\2'),           # "3 series" → "3series"
        (r'(\w+)(\d+)', r'\1 \2'),             # "es350" → "es 350"
        (r'(\d+)(\w+)', r'\1 \2'),             # "3series" → "3 series"
    ]
    
    for pattern, replacement in number_patterns:
        for var in list(variations):
            match = re.search(pattern, var)
            if match:
                new_var = re.sub(pattern, replacement, var)
                variations.add(new_var)
    
    # 6. Common automotive abbreviations and alternate forms (be more selective)
    abbreviation_maps = {
        'turbo': ['t'],
        'hybrid': ['h'],
        'electric': ['ev', 'e'],
        'awd': ['all wheel drive', '4wd'],
        'suv': ['sport utility'],
        'coupe': ['coup'],
    }
    
    # Only apply abbreviations to complete words, not partial matches
    for abbrev, expansions in abbreviation_maps.items():
        for var in list(variations):
            # Split into words to avoid partial replacements
            words = var.split()
            new_words = words.copy()
            
            # Check each word for exact matches
            for i, word in enumerate(words):
                if word == abbrev:
                    for expansion in expansions:
                        temp_words = words.copy()
                        temp_words[i] = expansion
                        new_var = ' '.join(temp_words)
                        variations.add(new_var)
                elif word in expansions:
                    temp_words = words.copy()
                    temp_words[i] = abbrev
                    new_var = ' '.join(temp_words)
                    variations.add(new_var)
    
    # Convert back to sorted list and remove empty strings
    result = sorted([v for v in variations if v and len(v) > 1])
    
    logger.info(f"🔧 Generated {len(result)} model variations for '{make} {model}': {result[:10]}{'...' if len(result) > 10 else ''}")
    
    return result 