import { RecommendationDatabase } from '../types';

export const MOCK_PRODUCT_DB: RecommendationDatabase = {
  dog: {
    default: [
      {
        id: 'dog-toy-1',
        name: 'Indestructible Chew Bone',
        category: 'toys',
        imageUrl: 'https://placehold.co/400x400?text=Dog+Toy',
        price: 14.99,
        affiliateLink: '#'
      },
      {
        id: 'dog-food-1',
        name: 'Premium Beef Kibble',
        category: 'food',
        imageUrl: 'https://placehold.co/400x400?text=Dog+Food',
        price: 49.99,
        affiliateLink: '#'
      },
      {
        id: 'dog-acc-1',
        name: 'Reflective Safety Harness',
        category: 'accessories',
        imageUrl: 'https://placehold.co/400x400?text=Dog+Harness',
        price: 24.99,
        affiliateLink: '#'
      }
    ],
    breeds: {}
  },
  cat: {
    default: [
      {
        id: 'cat-acc-1',
        name: 'Cozy Window Hammock',
        category: 'accessories',
        imageUrl: 'https://placehold.co/400x400?text=Cat+Hammock',
        price: 29.99,
        affiliateLink: '#'
      },
      {
        id: 'cat-toy-1',
        name: 'Feather Wand Teaser',
        category: 'toys',
        imageUrl: 'https://placehold.co/400x400?text=Cat+Toy',
        price: 8.99,
        affiliateLink: '#'
      },
      {
        id: 'cat-food-1',
        name: 'Salmon Pate Cans',
        category: 'food',
        imageUrl: 'https://placehold.co/400x400?text=Cat+Food',
        price: 22.99,
        affiliateLink: '#'
      }
    ],
    breeds: {}
  },
  fallback: [
    {
      id: 'gen-food-1',
      name: 'Premium Universal Pet Treats',
      category: 'food',
      imageUrl: 'https://placehold.co/400x400?text=Pet+Treats',
      price: 9.99,
      affiliateLink: '#'
    }
  ]
};
