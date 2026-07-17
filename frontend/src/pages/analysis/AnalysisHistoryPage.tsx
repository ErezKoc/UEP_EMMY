import PlaceholderPage from "../../components/layout/PlaceholderPage";

// Member 4 (AI analysis): past analyses of the current user.
// Needs a GET /v1/analysis list endpoint (the backend already stores every run in
// the AIAnalysisLog table — only the read endpoint is missing).
export default function AnalysisHistoryPage() {
  return (
    <PlaceholderPage
      title="Analysis history"
      owner="Member 4"
      description="List of past AI analyses (thumbnail, species/breed/age, date), filterable by pet, each linking back to its full result."
    />
  );
}
