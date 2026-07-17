import { useState } from "react";
import AnalysisCard from "../../components/AnalysisCard";
import ImageUpload from "../../components/ImageUpload";
import type { AnalysisResponse } from "../../types";

// Member 4 (AI analysis): this page already works end-to-end against the mock analyzer.
// Your scope: add a "which pet is this?" selector (Member 3's pets), a real progress
// indicator, an "analyze another" reset, and a "share to community" action that opens
// Member 5's create-post flow pre-filled with the image and result summary.
export default function AnalyzePage() {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Analyze a pet photo</h1>
      <ImageUpload onAnalysisComplete={setAnalysis} />
      <AnalysisCard analysis={analysis} />
    </div>
  );
}
