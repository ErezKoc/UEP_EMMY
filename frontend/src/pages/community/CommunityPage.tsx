import { Link } from "react-router-dom";
import CommunityFeed from "../../components/CommunityFeed";
import { PlusIcon } from "../../components/ui";

export default function CommunityPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Community</h1>
          <p className="mt-1 text-sm text-slate-500">
            Ask pet owners and veterinary professionals for their perspective.
          </p>
        </div>
        <Link
          to="/community/new"
          className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
        >
          <PlusIcon className="h-4 w-4" />
          New post
        </Link>
      </div>
      <div className="mt-6">
        <CommunityFeed />
      </div>
    </div>
  );
}
