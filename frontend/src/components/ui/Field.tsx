import { useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const CONTROL_CLASSES =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100 disabled:bg-slate-50 disabled:text-slate-400";

interface FieldWrapperProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

function FieldWrapper({ id, label, hint, error, children }: FieldWrapperProps) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-1 text-xs text-rose-600" role="alert">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>
      )}
    </div>
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function Input({ label, hint, error, className = "", ...rest }: InputProps) {
  const id = useId();
  return (
    <FieldWrapper id={id} label={label} hint={hint} error={error}>
      <input id={id} className={`${CONTROL_CLASSES} ${className}`} {...rest} />
    </FieldWrapper>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function Textarea({ label, hint, error, className = "", ...rest }: TextareaProps) {
  const id = useId();
  return (
    <FieldWrapper id={id} label={label} hint={hint} error={error}>
      <textarea id={id} rows={4} className={`${CONTROL_CLASSES} ${className}`} {...rest} />
    </FieldWrapper>
  );
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
  error?: string;
  options: Array<{ value: string; label: string }>;
}

export function Select({ label, hint, error, options, className = "", ...rest }: SelectProps) {
  const id = useId();
  return (
    <FieldWrapper id={id} label={label} hint={hint} error={error}>
      <select id={id} className={`${CONTROL_CLASSES} ${className}`} {...rest}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldWrapper>
  );
}
