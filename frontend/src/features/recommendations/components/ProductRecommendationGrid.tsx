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
            <div className="aspect-square w-full overflow-hidden rounded-lg bg-slate-100 mb-4 relative">
              <img 
                src={product.imageUrl} 
                alt={`Image of ${product.name}`} 
                className="h-full w-full object-cover object-center group-hover:opacity-75 transition-opacity"
              />
              <span className="absolute top-2 left-2 inline-flex items-center rounded-full bg-slate-900/80 px-2.5 py-0.5 text-xs font-medium text-white backdrop-blur-sm">
                {product.category}
              </span>
            </div>
            
            <h4 className="font-semibold text-slate-900 line-clamp-2" title={product.name}>{product.name}</h4>
            
            {product.ratings !== undefined && (
              <div className="flex items-center gap-1 mt-1 mb-2 text-sm text-slate-600">
                <span className="text-yellow-500">★</span>
                <span className="font-medium text-slate-900">{product.ratings}</span>
                <span>({product.no_of_ratings})</span>
              </div>
            )}
            
            <div className="flex flex-col gap-3 mt-auto pt-4">
              <span className="font-bold text-lg text-slate-900">${(product.price || 0).toFixed(2)}</span>
              
              <a 
                href={product.affiliateLink || `https://www.amazon.in/s?k=${encodeURIComponent(product.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 bg-primary-600 text-white hover:bg-primary-700 focus-visible:outline-primary-600 px-4 py-2 text-sm"
                aria-label={`Check ${product.name} on Amazon`}
              >
                Check Live on Amazon
              </a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
