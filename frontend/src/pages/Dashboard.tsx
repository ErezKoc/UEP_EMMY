import { useEffect, useState } from "react";
import { getReminders } from "../api/client";
import AnalysisCard from "../components/AnalysisCard";
import CommunityFeed from "../components/CommunityFeed";
import GettingStarted from "../components/GettingStarted";
import ImageUpload from "../components/ImageUpload";
import UpcomingReminders from "../components/UpcomingReminders";
import type { AnalysisResponse, Reminder } from "../types";

export default function Dashboard() {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  /*
   * Fetched once, here, and handed to both the checklist and the upcoming-care
   * panel. They each used to fetch it themselves — the same list twice on one
   * page load, against a six-connection budget the page was already exceeding.
   */
  const [reminders, setReminders] = useState<Reminder[]>([]);

  useEffect(() => {
    let cancelled = false;
    getReminders()
      .then((items) => {
        if (!cancelled) setReminders(items);
      })
      .catch(() => {
        // The panels render their own empty states; a failure here is not
        // worth an error banner across the dashboard.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      {/*
        Above the grid, full width, and first. A new account used to land on
        four widgets aimed at somebody who already had pets — including a photo
        upload box offered to a person with nothing to photograph yet. This
        removes itself once the steps are done, so it costs an established
        member nothing.
      */}
      <GettingStarted reminderCount={reminders.length} />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <ImageUpload onAnalysisComplete={setAnalysis} />
          <AnalysisCard analysis={analysis} />
          <UpcomingReminders items={reminders} />
        </div>

        <CommunityFeed compact />
      </div>
    </div>
  );
}
