export type SpeciesType = 'cat' | 'dog';

export type ProductCategory = 'food' | 'toys' | 'accessories';

export interface Product {
  id: string;
  name: string;
  category: ProductCategory;
  imageUrl: string;
  price: number;
  affiliateLink: string;
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
