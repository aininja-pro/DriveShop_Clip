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
    - "Crown Signia Limited" → ["crown signia limited", "crown signia", "signia", ...]
    
    Args:
        make: Vehicle make (e.g., "Lexus", "Mazda", "BMW")
        model: Vehicle model (e.g., "ES 350", "CX-90", "3 Series", "Crown Signia Limited")
        
    Returns:
        List of normalized model variations to search for
    """
    make_lower = make.lower()
    model_lower = model.lower()
    
    variations = set()  # Use set to avoid duplicates
    
    # Common trim level indicators to detect and handle
    TRIM_INDICATORS = {
        'limited', 'sport', 'touring', 'premium', 'base', 'deluxe',
        'platinum', 'titanium', 'signature', 'select', 'preferred',
        'elite', 'ultimate', 'luxury', 'executive', 'technology',
        # Lexus/Toyota specific
        'le', 'xle', 'se', 'xse', 'trd', 'sr', 'sr5',
        # Honda specific
        'lx', 'ex', 'ex-l', 'touring', 'sport', 
        # Mazda specific
        'gs', 'gt', 'signature', 'turbo',
        # General
        's', 'sv', 'sl', 'pro-4x', 'laramie', 'lariat', 'king ranch'
    }
    
    # 1. Basic model as-is
    variations.add(model_lower)
    
    # 2. Handle trim levels - generate variations without trim indicators
    # Split model into words to check for trim indicators
    model_words = model_lower.split()
    if len(model_words) > 1:
        # Special handling for multi-word trim indicators
        multi_word_trims = ['f sport', 'king ranch']
        has_trim = False
        base_model = model_lower
        
        # Check for multi-word trims first
        for trim in multi_word_trims:
            if trim in model_lower:
                base_model = model_lower.replace(trim, '').strip()
                has_trim = True
                break
        
        # If no multi-word trim found, check single words from the end
        if not has_trim:
            # Check from the end of the model name for trim indicators
            for i in range(len(model_words) - 1, -1, -1):
                word = model_words[i]
                clean_word = word.replace('-', '').lower()
                
                if clean_word in TRIM_INDICATORS:
                    # Found a trim indicator, everything before this is the base model
                    base_model_words = model_words[:i]
                    if base_model_words:  # Only if we have a base model left
                        base_model = ' '.join(base_model_words)
                        has_trim = True
                        break
        
        # If we found a trim indicator and have a base model, add variations without trim
        if has_trim and base_model and base_model != model_lower:
            variations.add(base_model)  # "crown signia"
            variations.add(base_model.replace(' ', ''))  # "crownsignia"
            variations.add(base_model.replace(' ', '-'))  # "crown-signia"
            if '-' in base_model:
                variations.add(base_model.replace('-', ' '))  # Handle hyphenated models
                variations.add(base_model.replace('-', ''))
            
            logger.info(f"🔧 Detected trim level in '{model}' - added base model variation: '{base_model}'")
    
    # 3. Handle spaces vs no spaces
    model_no_spaces = model_lower.replace(' ', '')
    model_with_spaces = model_lower
    
    variations.add(model_no_spaces)          # "es350", "cx90"
    variations.add(model_with_spaces)        # "es 350", "cx-90"
    
    # 4. Handle hyphens vs spaces vs no separator
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
    
    # 5. Add make prefix variations
    for var in list(variations):
        variations.add(f"{make_lower} {var}")     # "lexus es350", "mazda cx90"
        variations.add(f"{make_lower}{var}")      # "lexuses350", "mazdacx90"
        if ' ' not in var:  # Only add hyphen for no-space variants
            variations.add(f"{make_lower}-{var}") # "lexus-es350", "mazda-cx90"
    
    # 6. Handle numeric patterns (like "3 Series" vs "3Series")
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
    
    # 7. Common automotive abbreviations and alternate forms (be more selective)
    abbreviation_maps = {
        'turbo': ['t'],
        # Removed 'h' abbreviation for hybrid - it's too ambiguous and causes issues
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