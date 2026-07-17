import { useRef, useState } from "react";
import type { DragEvent, ChangeEvent } from "react";
import { ApiError, uploadForAnalysis } from "../api/client";
import { ImageIcon } from "./ui/icons";
import type { AnalysisResponse } from "../types";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIZE_MB = 10;

interface ImageUploadProps {
  onAnalysisComplete: (analysis: AnalysisResponse) => void;
}

export default function ImageUpload({ onAnalysisComplete }: ImageUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = async (file: File) => {
    setError(null);

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError("Please choose a JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Image must be smaller than ${MAX_SIZE_MB} MB.`);
      return;
    }

    setPreviewUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return URL.createObjectURL(file);
    });

    setIsUploading(true);
    try {
      const analysis = await uploadForAnalysis(file);
      onAnalysisComplete(analysis);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Is the backend running?");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void processFile(file);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) void processFile(file);
    event.target.value = "";
  };

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <h2 className="text-lg font-semibold text-slate-800">Analyze a pet photo</h2>
      <p className="mt-1 text-sm text-slate-500">
        Upload a photo and our AI will estimate species, breed, and age.
      </p>

      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a pet image"
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") fileInputRef.current?.click();
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`mt-4 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
          isDragging
            ? "border-indigo-500 bg-indigo-50"
            : "border-slate-300 bg-slate-50 hover:border-indigo-400 hover:bg-indigo-50/50"
        }`}
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt="Selected pet"
            className="max-h-40 rounded-lg object-contain"
          />
        ) : (
          <>
            <ImageIcon className="h-8 w-8 text-slate-400" />
            <p className="mt-2 text-sm font-medium text-slate-700">
              Drag &amp; drop a pet photo here
            </p>
            <p className="text-xs text-slate-500">or click to browse — JPEG, PNG, WebP up to 10 MB</p>
          </>
        )}

        {isUploading && (
          <p className="mt-3 text-sm font-medium text-indigo-600" role="status">
            Analyzing image…
          </p>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        onChange={handleFileChange}
        className="hidden"
      />

      {error && (
        <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
