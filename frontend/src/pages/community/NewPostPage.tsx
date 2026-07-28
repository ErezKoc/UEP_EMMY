import { useLocation } from "react-router-dom";
import PlaceholderPage from "../../components/layout/PlaceholderPage";
import type { PostPrefill } from "../../types";

// Member 5 (Community & vets): create-post form (POST /v1/posts already exists).
//
// Member 4's "Share to community" button navigates here with route state:
//   const prefill = (useLocation().state as { prefill?: PostPrefill } | null)?.prefill;
// `prefill` (types/index.ts) carries analysis_id, image_url, and a suggested
// title + content — use them as the form's initial values.
export default function NewPostPage() {
  const location = useLocation();
  const prefill = (location.state as { prefill?: PostPrefill } | null)?.prefill;

  return (
    <PlaceholderPage
      title="New post"
      owner="Member 5"
      description={
        prefill
          ? `Create-post form. (Share-to-community handoff received: "${prefill.title}" with the analyzed image — use it to pre-fill this form.)`
          : "Create-post form: title, body, optional image or attached AI analysis result."
      }
    />
  );
}
