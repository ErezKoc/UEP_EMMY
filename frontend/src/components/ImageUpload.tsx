import { useEffect, useRef, useState } from "react";
import type { DragEvent, ChangeEvent } from "react";
import { ApiError, uploadForAnalysis } from "../api/client";
import { ImageIcon } from "./ui/icons";
import type { AnalysisResponse, SymptomIntake } from "../types";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIZE_MB = 10;

// The analysis is a single request, so the bar is staged rather than measured:
// labels advance on a timer while we wait, and the last stage holds until the
// response lands. Honest enough for a demo, and far clearer than a bare spinner.
const PROGRESS_STAGES = [
  { label: "Uploading photo…", width: "25%" },
  { label: "Detecting species…", width: "55%" },
  { label: "Estimating breed and age…", width: "85%" },
];
const STAGE_INTERVAL_MS = 900;

interface ImageUploadProps {
  onAnalysisComplete: (analysis: AnalysisResponse) => void;
  /** Pet to link the analysis to (Member 4's pet picker). Omit for unlinked. */
  animalId?: string | null;
  /** Symptom answers assessed alongside the photo. Omit for breed-only. */
  intake?: SymptomIntake | null;
}

export default function ImageUpload({ onAnalysisComplete, animalId, intake }: ImageUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isUploading) return;
    setStageIndex(0);
    const timer = setInterval(() => {
      setStageIndex((current) => Math.min(current + 1, PROGRESS_STAGES.length - 1));
    }, STAGE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [isUploading]);

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
      const analysis = await uploadForAnalysis(file, animalId, intake);
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

  const stage = PROGRESS_STAGES[stageIndex];

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <h2 className="text-lg font-semibold text-slate-800">Analyze a dog or cat photo</h2>
      <p className="mt-1 text-sm text-slate-500">
        Upload a photo of a dog or cat and our AI will estimate the breed and age.
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
            ? "border-primary-500 bg-primary-50"
            : "border-slate-300 bg-slate-50 hover:border-primary-400 hover:bg-primary-50/50"
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
      </div>

      {isUploading && (
        <div className="mt-4" role="status" aria-live="polite">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-primary-700">{stage.label}</span>
            <span className="text-xs text-slate-400">
              step {stageIndex + 1} of {PROGRESS_STAGES.length}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-primary-500 transition-all duration-700 ease-out"
              style={{ width: stage.width }}
            />
          </div>
        </div>
      )}

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
