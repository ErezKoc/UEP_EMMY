from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from app.services.recommendation import get_diverse_recommendations

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"]
)

@router.get("/pet", response_model=List[Dict[str, Any]])
def get_recommendations_for_pet(
    species: str = Query(None, description="The species of the pet (e.g. 'Dog', 'Cat')")
):
    """
    Get top product recommendations based on the pet's species.
    Returns top 2 products for Food, Toys, and Accessories.
    """
    recommendations = get_diverse_recommendations(species)
    
    if not recommendations:
        return []
        
    return recommendations
