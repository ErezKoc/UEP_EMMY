import { AnalysisResponse } from '../../../types';
import { useProductRecommendations } from '../hooks/useProductRecommendations';
import ProductRecommendationGrid from './ProductRecommendationGrid';

interface ProductRecommendationSectionProps {
  analysis: AnalysisResponse;
}

export default function ProductRecommendationSection({ analysis }: ProductRecommendationSectionProps) {
  const species = analysis.result.species;
  const topBreed = analysis.result.breed_candidates?.[0]?.breed;

  const {
    products,
    isLoading,
    error
  } = useProductRecommendations(species, topBreed);

  return (
    <ProductRecommendationGrid
      products={products}
      isLoading={isLoading}
      error={error}
    />
  );
}
