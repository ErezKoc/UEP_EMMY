
import { Product } from '../types';

interface ProductRecommendationGridProps {
  products: Product[];
  isLoading: boolean;
  error?: string | null;
}

export default function ProductRecommendationGrid({
  products,
  isLoading,
  error
}: ProductRecommendationGridProps) {


  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-red-700 mt-8" role="alert">
        <p>We couldn't load recommendations right now. Please try again later.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="mt-8">
        <h3 className="text-xl font-bold text-slate-800 mb-6">
          Loading recommendations...
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 animate-pulse">
          {[1, 2, 3].map((n) => (
            <div key={n} className="h-64 bg-slate-200 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!products || products.length === 0) {
    return null;
  }

  return (
    <section aria-labelledby="recommendations-heading" className="mt-8">
      <h3 id="recommendations-heading" className="text-xl font-bold text-slate-800 mb-6">
        Recommended for your pet
      </h3>
      
      <ul role="list" className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
        {products.map((product) => (
          <li key={product.id} className="group relative rounded-xl border border-slate-200 p-4 hover:shadow-lg transition-shadow bg-white flex flex-col">
            <div className="aspect-square w-full overflow-hidden rounded-lg bg-slate-100 mb-4">
              <img 
                src={product.imageUrl} 
                alt={`Image of ${product.name}`} 
                className="h-full w-full object-cover object-center group-hover:opacity-75 transition-opacity"
              />
            </div>
            
            <h4 className="font-semibold text-slate-900">{product.name}</h4>
            <p className="text-slate-500 text-sm mb-4 capitalize">{product.category}</p>
            
            <div className="flex items-center justify-between mt-auto">
              <span className="font-bold text-lg text-slate-900">${product.price.toFixed(2)}</span>
              
              <a 
                href={product.affiliateLink}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                aria-label={`Buy ${product.name}`}
              >
                Buy Now
              </a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
