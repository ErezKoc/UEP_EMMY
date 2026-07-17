import CommunityFeed from "../../components/CommunityFeed";

// Member 5 (Community & vets): the feed below already works against /v1/posts.
// Your scope: pagination, search/filter by species or topic, a "New post" button
// linking to /community/new, and post cards linking to /community/:postId.
export default function CommunityPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Community</h1>
      <CommunityFeed />
    </div>
  );
}
