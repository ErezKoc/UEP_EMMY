import PlaceholderPage from "../../components/layout/PlaceholderPage";

// Member 5 (Community & vets): create-post form (POST /v1/posts already exists).
// Coordinate with Member 4: this page should accept a pre-filled image + AI summary
// when reached via "share to community" from an analysis result (e.g. via route state).
export default function NewPostPage() {
  return (
    <PlaceholderPage
      title="New post"
      owner="Member 5"
      description="Create-post form: title, body, optional image or attached AI analysis result."
    />
  );
}
