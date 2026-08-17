import { useState, useEffect } from 'react';
import { Product, SpeciesType } from '../types';
import { MOCK_PRODUCT_DB } from '../api/mockData';

export function useProductRecommendations(species: string | null | undefined, breed?: string) {
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError(null);

    // Simulate network delay
    const timer = setTimeout(() => {
      if (!isMounted) return;

      try {
        if (!species) {
          setProducts([]);
          setIsLoading(false);
          return;
        }

        const normalizedSpecies = species.toLowerCase();
        let fetchedProducts: Product[] = [];

        if (normalizedSpecies === 'cat' || normalizedSpecies === 'dog') {
          const speciesKey = normalizedSpecies as SpeciesType;
          fetchedProducts = MOCK_PRODUCT_DB[speciesKey]?.breeds?.[breed || ''] 
            || MOCK_PRODUCT_DB[speciesKey]?.default 
            || MOCK_PRODUCT_DB.fallback;
        } else {
          fetchedProducts = MOCK_PRODUCT_DB.fallback;
        }

        setProducts(fetchedProducts);
      } catch (err) {
        console.error('Error fetching recommendations', err);
        setError('Failed to load recommendations.');
      } finally {
        setIsLoading(false);
      }
    }, 800); // 800ms mock delay

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [species, breed]);



  return {
    products,
    isLoading,
    error
  };
}
