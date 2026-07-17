import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  description?: string;
  /** Rendered on the right side of the header row (e.g. an action button). */
  action?: ReactNode;
  className?: string;
  children?: ReactNode;
}

export default function Card({ title, description, action, className = "", children }: CardProps) {
  return (
    <section className={`rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-lg font-semibold text-slate-800">{title}</h2>}
            {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
