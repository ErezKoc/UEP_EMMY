import { useState } from "react";
import AnalysisCard from "../components/AnalysisCard";
import CommunityFeed from "../components/CommunityFeed";
import ImageUpload from "../components/ImageUpload";
import type { AnalysisResponse } from "../types";

export default function Dashboard() {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-6">
        <ImageUpload onAnalysisComplete={setAnalysis} />
        <AnalysisCard analysis={analysis} />
      </div>

      <CommunityFeed compact />
    </div>
  );
}
