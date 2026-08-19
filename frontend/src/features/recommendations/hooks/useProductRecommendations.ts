import { useState, useEffect } from 'react';
import { Product } from '../types';

export function useProductRecommendations(species: string | null | undefined, breed?: string) {
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    
    // We only care about species now as per your request!
    if (!species) {
      setProducts([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    const fetchRecommendations = async () => {
      try {
        // Fetch real recommendations from our FastAPI backend!
        const response = await fetch(`/v1/recommendations/pet?species=${encodeURIComponent(species)}&limit=6`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch recommendations: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (isMounted) {
          setProducts(data);
          setIsLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          console.error('Error fetching recommendations from API:', err);
          setError('Failed to load recommendations.');
          setIsLoading(false);
        }
      }
    };

    fetchRecommendations();

    return () => {
      isMounted = false;
    };
  }, [species]); // Removing breed dependency since we are just basing it on species

  return {
    products,
    isLoading,
    error
  };
}
