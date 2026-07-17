import type { ReactNode } from "react";

type Variant = "primary" | "neutral" | "success" | "warning" | "danger" | "vet";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-primary-50 text-primary-700",
  neutral: "bg-slate-100 text-slate-600",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-rose-50 text-rose-700",
  // Reserved for verified veterinarian markers across the app (Member 5).
  vet: "bg-teal-50 text-teal-700 ring-1 ring-teal-200",
};

export default function Badge({
  variant = "neutral",
  className = "",
  children,
}: {
  variant?: Variant;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
