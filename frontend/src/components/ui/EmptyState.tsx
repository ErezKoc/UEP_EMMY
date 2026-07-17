import type { ReactNode } from "react";
import { PawIcon } from "./icons";

interface EmptyStateProps {
  /** An icon element, typically from ui/icons. Defaults to the paw mark. */
  icon?: ReactNode;
  title: string;
  description?: string;
  /** Typically a Button that starts the relevant flow. */
  action?: ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        {icon ?? <PawIcon className="h-6 w-6" />}
      </span>
      <h3 className="mt-3 text-base font-semibold text-slate-700">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
