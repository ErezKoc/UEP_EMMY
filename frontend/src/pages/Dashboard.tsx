import { useState } from "react";
import AnalysisCard from "../components/AnalysisCard";
import CommunityFeed from "../components/CommunityFeed";
import ImageUpload from "../components/ImageUpload";
import type { AnalysisResponse } from "../types";

export default function Dashboard() {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4">
          <span className="text-2xl" aria-hidden>
            🐾
          </span>
          <div>
            <h1 className="text-xl font-bold text-slate-800">UEP EMMY</h1>
            <p className="text-xs text-slate-500">AI-assisted veterinary platform</p>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-2">
        <div className="space-y-6">
          <ImageUpload onAnalysisComplete={setAnalysis} />
          <AnalysisCard analysis={analysis} />
        </div>

        <CommunityFeed />
      </main>
    </div>
  );
}
