import os
import pandas as pd
from typing import List, Dict, Any
import logging
import uuid
import re

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "raw", "All Pet Supplies.csv")

# Global cache to avoid reading CSV on every request
_products_df = None

def _load_data_if_needed():
    global _products_df
    if _products_df is None:
        try:
            _products_df = pd.read_csv(DATA_PATH)
        except Exception as e:
            logger.error(f"Could not load data from {DATA_PATH}: {e}")

def _clean_price(price_str) -> float:
    """Helper to convert strings like '₹328' or '$15.99' to float."""
    if pd.isna(price_str) or not isinstance(price_str, str):
        return float(price_str) if pd.notna(price_str) else 0.0
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def get_diverse_recommendations(species: str = None) -> List[Dict[str, Any]]:
    global _products_df
    _load_data_if_needed()
    
    if _products_df is None:
        return []
        
    df = _products_df.copy()
    
    # 1. Helper function for keyword-based categorization & safety filtering
    def categorize_product(name: str) -> str:
        name_lower = str(name).lower()
        
        # Strict safety filter: Exclude medical/health items
        health_keywords = ['medicine', 'vitamin', 'tick', 'flea', 'health', 'supplement', 'dewormer', 'spray', 'healing']
        if any(k in name_lower for k in health_keywords):
            return 'Exclude'
            
        if any(k in name_lower for k in ['toy', 'ball', 'teaser', 'rope', 'plush', 'wand', 'mouse', 'feather']):
            return 'Toys & Play'
        if any(k in name_lower for k in ['shampoo', 'brush', 'comb', 'collar', 'leash', 'harness', 'bed', 'bowl', 'tag', 'feeder', 'litter', 'pad']):
            return 'Care & Accessories'
        if any(k in name_lower for k in ['food', 'biscuit', 'treat', 'chicken', 'fish', 'meat', 'mackerel', 'gravy', 'meal', 'bone', 'chews']):
            return 'Food & Treats'
        return 'Other'

    # Apply categorization
    df['category'] = df['name'].apply(categorize_product)
    
    # Clean numeric fields
    df['ratings'] = pd.to_numeric(df['ratings'], errors='coerce')
    df['no_of_ratings'] = pd.to_numeric(df['no_of_ratings'].astype(str).str.replace(',', ''), errors='coerce')
    
    # Optional species filter if provided
    if species:
        species_lower = species.lower()
        df = df[df['name'].str.lower().str.contains(species_lower, na=False)]

    # Filter to valid categories with proven review volume
    valid_df = df[
        (df['category'].isin(['Food & Treats', 'Toys & Play', 'Care & Accessories'])) &
        (df['no_of_ratings'] >= 50)
    ]
    
    # Collect top 2 best-reviewed items per category
    recommendations = []
    target_categories = ['Food & Treats', 'Toys & Play', 'Care & Accessories']
    
    for cat in target_categories:
        cat_df = valid_df[valid_df['category'] == cat]
        sorted_cat = cat_df.sort_values(by=['ratings', 'no_of_ratings'], ascending=[False, False])
        recommendations.append(sorted_cat.head(2))
        
    if not recommendations:
        return []
        
    final_df = pd.concat(recommendations)
    
    # Map to frontend interface
    results = []
    for _, row in final_df.iterrows():
        results.append({
            "id": str(uuid.uuid4()),
            "name": row['name'],
            "category": row['category'],
            "price": _clean_price(row.get('actual_price', row.get('discount_price', '0'))),
            "imageUrl": row['image'],
            "affiliateLink": row['link'],
            "ratings": row['ratings'] if pd.notna(row['ratings']) else 0.0,
            "no_of_ratings": int(row['no_of_ratings']) if pd.notna(row['no_of_ratings']) else 0
        })
        
    return results
