import os
import pickle
import pandas as pd
from typing import List, Dict, Any
import logging
import uuid
import re

logger = logging.getLogger(__name__)

# Define paths relative to this file's location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models", "recsys")
COSINE_SIM_PATH = os.path.join(MODEL_DIR, "cosine_sim.pkl")
PRODUCTS_DF_PATH = os.path.join(MODEL_DIR, "products_df.pkl")

# Global variables to hold the loaded models in memory
cosine_sim = None
products_df = None

def load_recsys_models():
    """Loads the recommendation models into memory."""
    global cosine_sim, products_df
    if cosine_sim is None or products_df is None:
        try:
            with open(COSINE_SIM_PATH, "rb") as f:
                cosine_sim = pickle.load(f)
            products_df = pd.read_pickle(PRODUCTS_DF_PATH)
            logger.info("Recommendation engine models loaded successfully into memory.")
        except FileNotFoundError:
            logger.warning(f"Recommendation models not found in {MODEL_DIR}. Please run the training script.")

def _clean_price(price_str) -> float:
    """Helper to convert strings like '₹328' or '$15.99' to float."""
    if not isinstance(price_str, str):
        return float(price_str) if pd.notna(price_str) else 0.0
    # Remove everything except digits and decimal point
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def _format_product(row: pd.Series, sim_score: float = None) -> Dict[str, Any]:
    """Helper to map our dataset row to the frontend Product interface."""
    return {
        "id": str(uuid.uuid4()), # Generate a unique ID for React keys
        "name": row['name'],
        "category": row['sub_category'],
        "price": _clean_price(row['discount_price']),
        "imageUrl": row['image'],
        "affiliateLink": row['link'],
        "similarity_score": round(sim_score, 2) if sim_score is not None else 1.0
    }

def get_recommendations_for_species(species: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Generic fallback recommendations for a given species (e.g. 'Dog')."""
    global products_df
    
    if products_df is None:
        load_recsys_models()
        
    if products_df is None or not species:
        return []
        
    # Search for the species in the product name (case-insensitive)
    mask = products_df['name'].str.lower().str.contains(species.lower(), na=False)
    filtered = products_df[mask]
    
    # If we couldn't find any specific to species, fallback to generic items
    if len(filtered) == 0:
        filtered = products_df.head(limit)
    else:
        filtered = filtered.head(limit)
        
    results = []
    for _, row in filtered.iterrows():
        results.append(_format_product(row))
        
    return results

def get_similar_products(product_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Returns a list of similar products given a specific product name."""
    global cosine_sim, products_df
    
    if cosine_sim is None or products_df is None:
        load_recsys_models()
        
    if cosine_sim is None or products_df is None:
        return [] 

    try:
        idx_matches = products_df[products_df['name'].str.lower() == product_name.lower()].index
        if len(idx_matches) == 0:
            return []
        idx = idx_matches[0]
    except Exception as e:
        logger.error(f"Error looking up product {product_name}: {e}")
        return []

    sim_scores = list(enumerate(cosine_sim[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    top_indices = [i[0] for i in sim_scores[1:limit+1]]
    
    results = []
    for i in top_indices:
        row = products_df.iloc[i]
        sim_val = float(sim_scores[1:limit+1][top_indices.index(i)][1])
        results.append(_format_product(row, sim_score=sim_val))
        
    return results
