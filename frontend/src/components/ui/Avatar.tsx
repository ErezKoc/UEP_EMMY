type Size = "sm" | "md" | "lg";

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-16 w-16 text-xl",
};

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

export default function Avatar({
  name,
  src,
  size = "md",
  className = "",
}: {
  name: string;
  src?: string | null;
  size?: Size;
  className?: string;
}) {
  if (src) {
    return (
      <img
        src={src}
        alt={name}
        className={`rounded-full object-cover ring-1 ring-slate-200 ${SIZE_CLASSES[size]} ${className}`}
      />
    );
  }
  return (
    <span
      aria-hidden
      className={`inline-flex items-center justify-center rounded-full bg-primary-100 font-semibold text-primary-700 ${SIZE_CLASSES[size]} ${className}`}
    >
      {initials(name) || "?"}
    </span>
  );
}
