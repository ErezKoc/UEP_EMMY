import EmptyState from "../ui/EmptyState";
import { WrenchIcon } from "../ui/icons";

interface PlaceholderPageProps {
  title: string;
  /** Which team member owns building this page. */
  owner: string;
  description: string;
}

/**
 * Route stub so every member's pages are reachable from day one.
 * Replace the stub with the real page component; the route already exists in App.tsx.
 */
export default function PlaceholderPage({ title, owner, description }: PlaceholderPageProps) {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold text-slate-800">{title}</h1>
      <div className="mt-6">
        <EmptyState
          icon={<WrenchIcon className="h-6 w-6" />}
          title={`Under construction — owned by ${owner}`}
          description={description}
        />
      </div>
    </div>
  );
}
