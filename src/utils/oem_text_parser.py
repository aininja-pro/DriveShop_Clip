"""
OEM Text Parser - Parses copy/pasted text from OEM documents
Extracts structured data matching our sentiment format
"""
import re
import json
from typing import Dict, List, Any
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class OEMTextParser:
    """Parse OEM text content into structured format"""
    
    def parse_mazda_format(self, text: str, model_name: str = None, default_year: int = 2025) -> Dict:
        """
        Parse Mazda one-pager format text
        Expected format includes:
        - Model name and positioning
        - PURCHASE REASONS section
        - KEY VALUES & FEATURE HIGHLIGHTS
        - Customer profile info
        
        Args:
            text: The OCR extracted text
            model_name: Model name if known (e.g., "CX-50")
            default_year: Default year if not found in text (default: 2025)
        """
        
        # Detect model if not provided
        if not model_name:
            model_match = re.search(r'(CX-\d+|MX-\d+|MAZDA\d+)', text, re.IGNORECASE)
            model_name = model_match.group(1).upper() if model_match else "Unknown"
        
        # Try to detect year from text
        year_patterns = [
            r'(?:MY|Model Year|Year)[:\s]*(\d{4})',
            r'(\d{4})\s+(?:Model|MY)',
            r'(\d{4})\s+' + re.escape(model_name),
            r'\b(202[3-6])\b'  # Look for years 2023-2026
        ]
        
        detected_year = None
        for pattern in year_patterns:
            year_match = re.search(pattern, text, re.IGNORECASE)
            if year_match:
                detected_year = int(year_match.group(1))
                logger.info(f"Detected year {detected_year} for model {model_name}")
                break
        
        # Special case: MX-5 is typically a year behind
        if model_name == "MX-5" and not detected_year:
            detected_year = default_year - 1
        
        result = {
            "make": "Mazda",
            "model": model_name,
            "year": detected_year or default_year,
        }
        
        # Extract positioning statement
        # Usually at the beginning, before PURCHASE REASONS
        positioning_match = re.search(
            rf"{model_name}[^.]*?(?:serves as|is|provides|offers)([^.]+)\.",
            text,
            re.IGNORECASE
        )
        if positioning_match:
            result["positioning_statement"] = f"{model_name} {positioning_match.group(0)}"
        
        # Extract target audience
        audience_patterns = [
            r"(?:CUSTOMER|TARGET|BUYER).*?(?:PROFILE|AUDIENCE)[:\s]*([^\n]+)",
            r"(?:designed for|targeted at|appeals to)\s+([^.]+)",
        ]
        for pattern in audience_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["target_audience"] = match.group(1).strip()
                break
        
        # Extract purchase reasons
        purchase_drivers = []
        reasons_match = re.search(
            r"PURCHASE REASONS[:\s]*\n((?:(?:\d+\.|\•|\-)[^\n]+\n?)+)",
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if reasons_match:
            reasons_text = reasons_match.group(1)
            reason_lines = re.findall(r"(?:\d+\.|\•|\-)?\s*([^\n]+)", reasons_text)
            
            for i, reason in enumerate(reason_lines):
                if reason.strip():
                    purchase_drivers.append({
                        "reason": reason.strip().lower(),
                        "priority": i + 1,
                        "target_audience": result.get("target_audience", ""),
                        "messaging": ""
                    })
        
        result["purchase_drivers_intended"] = purchase_drivers
        
        # Extract key features
        key_features = []
        
        # Method 1: Look for KEY VALUES section
        features_match = re.search(
            r"KEY (?:VALUES|FEATURES)[^:]*[:\s]*\n((?:(?:\d+\.|\•|\-)[^\n]+\n?)+)",
            text,
            re.IGNORECASE | re.MULTILINE
        )
        
        if features_match:
            features_text = features_match.group(1)
            feature_lines = re.findall(r"(?:\d+\.|\•|\-)?\s*([^\n]+)", features_text)
            
            for feature in feature_lines:
                if feature.strip():
                    # Categorize the feature
                    category = self._categorize_feature(feature)
                    key_features.append({
                        "feature": feature.strip(),
                        "category": category,
                        "priority": "primary" if len(key_features) < 3 else "secondary",
                        "messaging": feature.strip(),
                        "target_sentiment": "positive"
                    })
        
        # Method 2: Extract features from content
        feature_patterns = {
            "performance": [
                r"(\d+(?:\.\d+)?[- ]?(?:liter|L|turbo|hp|horsepower|lb-ft|torque))",
                r"((?:manual|automatic|AWD|all-wheel|4WD) (?:transmission|drive))",
                r"((?:sport|dynamic|performance) (?:mode|tuned|suspension))"
            ],
            "technology": [
                r"(\d+(?:\.\d+)?[- ]?inch (?:display|screen|infotainment))",
                r"((?:wireless|Android|Apple|CarPlay|smartphone) (?:integration|connectivity))",
                r"((?:adaptive|smart|advanced) (?:cruise|safety|driver))"
            ],
            "design": [
                r"((?:panoramic|power|sliding) (?:moonroof|sunroof|roof))",
                r"((?:LED|adaptive|signature) (?:headlights|lighting|lights))",
                r"((?:leather|premium|sport) (?:seats|interior|trim))"
            ]
        }
        
        # Find additional features in text
        for category, patterns in feature_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    feature_text = match if isinstance(match, str) else match[0]
                    if not any(f["feature"].lower() in feature_text.lower() for f in key_features):
                        key_features.append({
                            "feature": feature_text,
                            "category": category,
                            "priority": "secondary",
                            "messaging": feature_text,
                            "target_sentiment": "positive"
                        })
        
        result["key_features_intended"] = key_features[:10]  # Limit to 10
        
        # Extract brand attributes
        brand_attributes = []
        attribute_keywords = {
            "premium": ["premium", "luxury", "upscale", "refined"],
            "sporty": ["sporty", "dynamic", "athletic", "performance"],
            "practical": ["practical", "versatile", "functional", "capable"],
            "innovative": ["innovative", "advanced", "cutting-edge", "modern"],
            "reliable": ["reliable", "dependable", "quality", "durable"]
        }
        
        text_lower = text.lower()
        for attribute, keywords in attribute_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                brand_attributes.append(attribute)
        
        result["brand_attributes_intended"] = brand_attributes
        
        # Extract competitive information
        competitors = []
        comp_patterns = [
            r"(?:compared to|versus|vs\.?|against)\s+(?:the\s+)?([A-Z]\w+\s+[A-Z]\w+)",
            r"(?:competes with|competitor[s]?(?:\s+include)?)[:\s]+([^.]+)"
        ]
        
        for pattern in comp_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                competitors.extend(re.findall(r"([A-Z]\w+\s+[A-Z0-9\-]+)", match))
        
        result["competitive_positioning"] = {
            "competitors": list(set(competitors)),
            "market_positioning": result.get("positioning_statement", "")
        }
        
        return result
    
    def _categorize_feature(self, feature_text: str) -> str:
        """Categorize a feature based on keywords"""
        feature_lower = feature_text.lower()
        
        categories = {
            "performance": ["engine", "turbo", "hp", "torque", "transmission", "awd", "4wd", "speed"],
            "technology": ["display", "screen", "connect", "wireless", "smart", "digital", "tech"],
            "safety": ["safety", "airbag", "collision", "brake", "assist", "monitor", "alert"],
            "design": ["design", "style", "interior", "exterior", "seat", "wheel", "color"],
            "comfort": ["comfort", "quiet", "smooth", "climate", "heated", "cooled", "massage"],
            "utility": ["cargo", "space", "towing", "storage", "capacity", "versatile"]
        }
        
        for category, keywords in categories.items():
            if any(keyword in feature_lower for keyword in keywords):
                return category
        
        return "other"

# Example usage
if __name__ == "__main__":
    parser = OEMTextParser()
    
    # Example Mazda CX-50 text (copy/pasted from PDF)
    sample_text = """
    CX-50 serves as Mazda's next step in off-road capable & outdoor adventure SUV.
    
    PURCHASE REASONS
    1. Interior Volume
    2. Exterior Styling  
    3. Value for Money
    4. All-Wheel Drive
    
    KEY VALUES & FEATURE HIGHLIGHTS
    • Standard i-Activ AWD
    • Available Panoramic Moonroof
    • 2.5L Turbo Engine (256 HP)
    • Off-Road & Meridian Editions
    
    TARGET CUSTOMER: Active lifestyle enthusiasts
    """
    
    result = parser.parse_mazda_format(sample_text, "CX-50")
    print(json.dumps(result, indent=2))