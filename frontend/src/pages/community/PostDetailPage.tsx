import { useParams } from "react-router-dom";
import PlaceholderPage from "../../components/layout/PlaceholderPage";

// Member 5 (Community & vets): full post with its comment thread.
// Backend endpoints GET /v1/posts/{id} and POST /v1/posts/{id}/comments already exist.
// Use <Badge variant="vet"> to highlight comments from veterinarians.
export default function PostDetailPage() {
  const { postId } = useParams();
  return (
    <PlaceholderPage
      title={`Post #${postId ?? "?"}`}
      owner="Member 5"
      description="Full post with image, author, comment thread, a comment form, and verified-vet badges on vet replies."
    />
  );
}
