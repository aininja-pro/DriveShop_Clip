"""
Utility functions for extracting trim information from model strings.
"""

import re
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Common trim level keywords that indicate a trim variant
TRIM_INDICATORS = [
    # Luxury/Premium trims
    'Limited', 'Platinum', 'Premium', 'Ultimate', 'Signature', 'Executive',
    'Elite', 'Touring', 'Grand Touring', 'Luxury', 'Reserve',
    
    # Sport/Performance trims
    'Sport', 'S', 'RS', 'ST', 'GT', 'GTI', 'Type R', 'Type S', 'SRT',
    'AMG', 'M Sport', 'M Performance', 'N Line', 'N', 'TRD', 'SS', 'Z71',
    'Raptor', 'Rebel', 'Trail Boss', 'AT4', 'Denali', 'R/T', 'SRT8',
    'Carbon Edition', 'Track Edition', 'Performance', 'Club',
    
    # Base/Standard trims
    'Base', 'S', 'SE', 'SEL', 'SL', 'SR', 'SV', 'LX', 'EX', 'EX-L',
    'LE', 'XLE', 'XSE', 'L', 'LS', 'LT', 'LTZ', 'DX', 'Sport', 'Value',
    
    # Off-road/Adventure trims
    'TrailHawk', 'Rubicon', 'Sahara', 'Overland', 'TRD Pro', 'TRD Off-Road',
    'Trail', 'Adventure', 'Wilderness', 'Badlands', 'Bronco Sport', 'Big Bend',
    'Black Diamond', 'Outer Banks', 'Wildtrak', 'Z71', 'ZR2', 'FX4',
    
    # Hybrid/Electric trims
    'Hybrid', 'Plug-in Hybrid', 'PHEV', 'EV', 'Electric', 'e-tron', 'EQS',
    'Prime', 'Energi', 'Blue', 'e', 'h', 'Eco', 'BlueDrive', 'GreenTec',
    
    # Body style indicators (often part of trim)
    'Sedan', 'Coupe', 'Convertible', 'Cabriolet', 'Roadster', 'Hatchback',
    'Wagon', 'Estate', 'Avant', 'Sportback', 'Gran Coupe', 'Gran Turismo',
    'Crew Cab', 'Double Cab', 'Extended Cab', 'Regular Cab', 'King Cab',
    'Quad Cab', 'SuperCab', 'SuperCrew', 'Access Cab',
    
    # Drivetrain (sometimes part of trim designation)
    'AWD', '4WD', 'FWD', 'RWD', '4MATIC', 'xDrive', 'Quattro', 'SH-AWD',
    
    # Special editions
    'Anniversary Edition', 'Special Edition', 'Launch Edition', 'First Edition',
    'Night Edition', 'Black Edition', 'Sport Edition',
    
    # Size/configuration
    'Long Range', 'Extended Range', 'Max', 'L', 'XL', 'Plus',
    
    # Specific model trims (MX-5 Miata example)
    'RF', 'Club RF', 'Grand Touring RF', 'Sport RF'
]

def extract_trim_from_model(model_string: str, make: str = "") -> Tuple[str, Optional[str]]:
    """
    Extract the base model and trim level from a combined model string.
    
    Examples:
        "MX-5 Miata Club RF" -> ("MX-5 Miata", "Club RF")
        "Camry XLE" -> ("Camry", "XLE")
        "F-150 Raptor Crew Cab" -> ("F-150", "Raptor Crew Cab")
        "Civic" -> ("Civic", None)
        
    Args:
        model_string: The full model string that may contain trim information
        make: The vehicle make (helps with brand-specific trim detection)
        
    Returns:
        Tuple of (base_model, trim) where trim may be None if not detected
    """
    if not model_string:
        return ("", None)
    
    original_model = model_string.strip()
    
    # Handle special cases for specific makes
    if make.lower() == "mazda":
        # Special handling for Mazda models
        if "MX-5" in model_string or "Miata" in model_string:
            # MX-5 Miata has specific trim patterns
            base = "MX-5 Miata"
            remaining = model_string.replace("MX-5 Miata", "").strip()
            if not remaining:
                remaining = model_string.replace("MX-5", "").replace("Miata", "").strip()
            if remaining:
                return (base, remaining)
            return (base, None)
        elif "CX-" in model_string:
            # Extract CX-30, CX-5, CX-50, CX-9, CX-90 base models
            match = re.search(r'(CX-\d+)', model_string)
            if match:
                base = match.group(1)
                remaining = model_string.replace(base, "").strip()
                if remaining:
                    return (base, remaining)
                return (base, None)
    
    # Generic approach: Look for known trim indicators
    model_parts = model_string.split()
    base_model_parts = []
    trim_parts = []
    found_trim = False
    
    for i, part in enumerate(model_parts):
        # Check if this part or combination with next parts matches a trim indicator
        if not found_trim:
            # Check current part
            if any(trim.lower() == part.lower() for trim in TRIM_INDICATORS):
                found_trim = True
                trim_parts = model_parts[i:]
                break
            
            # Check two-word combinations
            if i < len(model_parts) - 1:
                two_word = f"{part} {model_parts[i+1]}"
                if any(trim.lower() == two_word.lower() for trim in TRIM_INDICATORS):
                    found_trim = True
                    trim_parts = model_parts[i:]
                    break
            
            # Check three-word combinations
            if i < len(model_parts) - 2:
                three_word = f"{part} {model_parts[i+1]} {model_parts[i+2]}"
                if any(trim.lower() == three_word.lower() for trim in TRIM_INDICATORS):
                    found_trim = True
                    trim_parts = model_parts[i:]
                    break
            
            base_model_parts.append(part)
    
    if found_trim and trim_parts:
        base_model = " ".join(base_model_parts).strip()
        trim = " ".join(trim_parts).strip()
        
        # Don't return empty base model
        if not base_model:
            return (original_model, None)
        
        return (base_model, trim)
    
    # Fallback: Try to detect trim by position and common patterns
    # Many trims come after the base model name
    # e.g., "Accord LX", "Camry XLE", "F-150 Limited"
    
    # For 2-3 word models, check if last word(s) might be trim
    if len(model_parts) >= 2:
        # Check if last word is a potential trim
        last_word = model_parts[-1]
        if len(last_word) <= 4 and last_word.isupper():  # Like "LX", "EX", "S"
            base = " ".join(model_parts[:-1])
            return (base, last_word)
        
        # Check if last two words might be trim (e.g., "Crew Cab")
        if len(model_parts) >= 3:
            last_two = f"{model_parts[-2]} {model_parts[-1]}"
            if any(trim.lower() == last_two.lower() for trim in TRIM_INDICATORS):
                base = " ".join(model_parts[:-2])
                if base:
                    return (base, last_two)
    
    # No trim detected
    return (original_model, None)

def format_model_with_trim(base_model: str, trim: Optional[str]) -> str:
    """
    Format a model and trim for display or storage.
    
    Args:
        base_model: The base model name
        trim: The trim level (optional)
        
    Returns:
        Formatted string like "Model (Trim)" or just "Model" if no trim
    """
    if trim:
        return f"{base_model} ({trim})"
    return base_model