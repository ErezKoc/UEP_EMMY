from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from app.services.recommendation import get_similar_products, get_recommendations_for_species

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"]
)

@router.get("/", response_model=List[Dict[str, Any]])
def get_recommendations(
    product_name: str = Query(..., description="The exact name of the product to base recommendations on"),
    limit: int = Query(5, ge=1, le=20, description="Number of recommendations to return (max 20)")
):
    """
    Get similar product recommendations based on a product name using our Content-Based TF-IDF engine.
    """
    recommendations = get_similar_products(product_name, limit)
    
    if not recommendations:
        raise HTTPException(
            status_code=404, 
            detail=f"No recommendations found for '{product_name}'."
        )
        
    return recommendations

@router.get("/pet", response_model=List[Dict[str, Any]])
def get_recommendations_for_pet(
    species: str = Query(..., description="The species of the pet (e.g. 'Dog', 'Cat')"),
    limit: int = Query(5, ge=1, le=20, description="Number of recommendations to return (max 20)")
):
    """
    Get generic top product recommendations based purely on the pet's species.
    """
    recommendations = get_recommendations_for_species(species, limit)
    
    if not recommendations:
        # Fallback empty list if dataset doesn't have anything
        return []
        
    return recommendations
