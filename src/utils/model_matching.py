"""
Scalable model matching for vehicle names with variations.
Handles thousands of models without hardcoding.
"""

import re
from typing import List, Tuple, Set

def generate_model_variations(model: str) -> Set[str]:
    """
    Generate common variations of a model name.
    Works for ANY model, not hardcoded.
    
    Examples:
    - "GTR T-Spec" → ["gtr t-spec", "gt-r t-spec", "gtr tspec", "gt r t spec"]
    - "CX-50" → ["cx-50", "cx 50", "cx50"]
    - "Model 3" → ["model 3", "model3", "model-3"]
    - "F-150" → ["f-150", "f 150", "f150"]
    """
    variations = set()
    model_lower = model.lower()
    variations.add(model_lower)
    
    # Special case: Add hyphen before last letter if it looks like a model code
    # GTR → GT-R, AMG → AM-G, TRD → TR-D, STI → ST-I
    words = model_lower.split()
    new_words = []
    for word in words:
        # If word is 3+ letters and all letters (like GTR, AMG)
        if len(word) >= 3 and word.isalpha():
            # Add variation with hyphen before last letter
            hyphenated = word[:-1] + '-' + word[-1]
            variations.add(model_lower.replace(word, hyphenated))
        new_words.append(word)
    
    model_lower_variants = [model_lower]
    
    # Apply transformations to all base variants
    for base in model_lower_variants:
        variations.add(base)
        
        # Handle hyphens: "GT-R" ↔ "GTR" ↔ "GT R"
        if '-' in base:
            variations.add(base.replace('-', ''))  # Remove hyphens
            variations.add(base.replace('-', ' '))  # Replace with space
        
        # Handle spaces: "Model 3" ↔ "Model3" ↔ "Model-3"
        if ' ' in base:
            variations.add(base.replace(' ', ''))  # Remove spaces
            variations.add(base.replace(' ', '-'))  # Replace with hyphen
    
    # Handle numbers: Add/remove spaces before numbers
    # "CX50" → "CX 50", "Model3" → "Model 3"
    spaced_version = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', model_lower)
    if spaced_version != model_lower:
        variations.add(spaced_version)
    
    # "CX 50" → "CX50", "Model 3" → "Model3"
    no_space_version = re.sub(r'([a-zA-Z])\s+(\d)', r'\1\2', model_lower)
    if no_space_version != model_lower:
        variations.add(no_space_version)
    
    # Handle common transcription errors and phonetic variations
    # "Emira" might be heard as "Amir", "Amira", etc.
    phonetic_variations = {
        'emira': ['amir', 'amira', 'amera'],
        'cayenne': ['cayenne', 'cayene', 'cayen'],
        'macan': ['makan', 'macann'],
        'giulia': ['julia', 'guilia'],
    }
    
    for original, alternates in phonetic_variations.items():
        if original in model_lower:
            for alt in alternates:
                variations.add(model_lower.replace(original, alt))
    
    # Handle common abbreviations in model names
    # "T-Spec" → "T-Special", etc.
    # Only do whole word replacements to avoid "Signature" → "Sigaturenature"
    words = model_lower.split()
    for i, word in enumerate(words):
        # Check abbreviations
        if word == 'spec':
            new_words = words.copy()
            new_words[i] = 'special'
            variations.add(' '.join(new_words))
        elif word == 'special':
            new_words = words.copy()
            new_words[i] = 'spec'
            variations.add(' '.join(new_words))
        elif word == 'perf':
            new_words = words.copy()
            new_words[i] = 'performance'
            variations.add(' '.join(new_words))
    
    return variations

def extract_model_components(model: str) -> Tuple[str, List[str]]:
    """
    Extract base model and trim/variant components.
    
    Examples:
    - "Camry XLE V6" → ("camry", ["xle", "v6"])
    - "F-150 Raptor" → ("f-150", ["raptor"])
    - "Model S Plaid" → ("model s", ["plaid"])
    """
    model_lower = model.lower()
    words = model_lower.split()
    
    if not words:
        return model_lower, []
    
    # Common trim indicators that suggest everything after is a trim
    trim_indicators = {'base', 'sport', 'touring', 'limited', 'premium', 
                      'ltd', 's', 't', 'se', 'le', 'xle', 'sr', 'sr5',
                      'lx', 'ex', 'si', 'type', 'gt', 'st', 'rs'}
    
    # Find where trim likely starts
    base_end_idx = len(words)
    for i, word in enumerate(words):
        if word in trim_indicators or any(char.isdigit() for char in word):
            base_end_idx = i
            break
    
    base_model = ' '.join(words[:base_end_idx]) if base_end_idx > 0 else model_lower
    trim_parts = words[base_end_idx:] if base_end_idx < len(words) else []
    
    return base_model, trim_parts

def fuzzy_model_match(search_text: str, model: str, threshold: float = 0.6) -> bool:
    """
    Intelligent model matching that works for any vehicle model.
    
    Args:
        search_text: Text to search in (transcript, title, etc.)
        model: Model name to search for
        threshold: How many components must match (0.6 = 60%)
        
    Returns:
        True if model is found with sufficient confidence
    """
    search_text = search_text.lower()
    
    # Generate variations
    variations = generate_model_variations(model)
    
    # Direct match with any variation
    for variation in variations:
        if variation in search_text:
            return True
    
    # Component-based matching for complex models
    base_model, trim_parts = extract_model_components(model)
    
    # For models with specific trim levels, check base model first
    if base_model:
        base_variations = generate_model_variations(base_model)
        base_found = any(var in search_text for var in base_variations)
        
        # If we found the base model and it has trim parts
        if base_found and trim_parts:
            # Check if any trim parts are mentioned
            trim_found = False
            for trim in trim_parts:
                if len(trim) > 2:  # Skip very short parts
                    trim_variations = generate_model_variations(trim)
                    if any(var in search_text for var in trim_variations):
                        trim_found = True
                        break
            
            # Base model found + at least one trim part = match
            if trim_found:
                return True
            # Just base model without trim = partial match (configurable)
            elif threshold <= 0.5:
                return True
        elif base_found and not trim_parts:
            # Simple model with no trim levels
            return True
    
    return False

def get_make_synonyms(make: str) -> Set[str]:
    """
    Get common synonyms and abbreviations for car makes.
    This is the ONLY place we maintain make-specific knowledge.
    """
    make_lower = make.lower()
    
    # Common abbreviations (this is the only hardcoded part)
    make_map = {
        'volkswagen': {'vw', 'volkswagon', 'v.w.'},
        'mercedes-benz': {'mercedes', 'benz', 'mb', 'merc'},
        'bmw': {'bimmer', 'beemer', 'bayerische'},
        'chevrolet': {'chevy', 'chev'},
        'general motors': {'gm', 'gmc'},
        'ford': {'fomoco'},
        'mazda': {'zoom-zoom'},  # Their old slogan
        'subaru': {'subie', 'scooby'},
        'mitsubishi': {'mitsu'},
        'alfa romeo': {'alfa'},
        'land rover': {'landy'},
        'rolls-royce': {'rolls', 'rr'},
    }
    
    # Return synonyms if found, otherwise just the make itself
    return make_map.get(make_lower, {make_lower}) | {make_lower}

# Example usage
if __name__ == "__main__":
    # Test various models
    test_cases = [
        ("GTR T-Spec", "The GT-R T-Spec is amazing"),
        ("CX-50", "I love the CX50 turbo"),
        ("Model 3 Performance", "My Model3 Performance is fast"),
        ("F-150 Raptor", "The F150 raptor is a beast"),
        ("Accord Hybrid Touring", "2024 accord hybrid is efficient"),
        ("Crown Signia", "The crown is Toyota's flagship"),
    ]
    
    print("Model Variation Testing:")
    print("="*60)
    
    for model, text in test_cases:
        variations = generate_model_variations(model)
        matches = fuzzy_model_match(text, model)
        print(f"\nModel: {model}")
        print(f"Text: {text}")
        print(f"Variations: {list(variations)[:3]}...")
        print(f"Match: {matches}")