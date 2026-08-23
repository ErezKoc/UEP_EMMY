export type SpeciesType = 'cat' | 'dog';

export type ProductCategory = string;

export interface Product {
  id: string;
  name: string;
  category: ProductCategory;
  imageUrl: string;
  price: number;
  affiliateLink: string;
  ratings?: number;
  no_of_ratings?: number;
}

export interface SpeciesRecommendationNode {
  default: Product[];
  breeds?: Record<string, Product[]>;
}

export type RecommendationDatabase = {
  [K in SpeciesType]: SpeciesRecommendationNode;
} & {
  fallback: Product[];
};
