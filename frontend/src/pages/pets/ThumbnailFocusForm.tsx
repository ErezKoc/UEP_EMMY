import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent, PointerEvent } from "react";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui";
import type { Animal } from "../../types";

interface ThumbnailFocusFormProps {
  pet: Animal;
  onSubmit: (positionX: number, positionY: number, zoom: number) => Promise<void>;
  onCancel: () => void;
}

interface PointerPosition {
  x: number;
  y: number;
}

const clamp = (value: number) => Math.min(100, Math.max(0, value));
const clampZoom = (value: number) => Math.min(3, Math.max(1, value));

export default function ThumbnailFocusForm({ pet, onSubmit, onCancel }: ThumbnailFocusFormProps) {
  const cropAreaRef = useRef<HTMLDivElement | null>(null);
  const pointerRef = useRef<PointerPosition | null>(null);
  const [positionX, setPositionX] = useState(pet.photo_position_x);
  const [positionY, setPositionY] = useState(pet.photo_position_y);
  const [zoom, setZoom] = useState(pet.photo_zoom);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const cropArea = cropAreaRef.current;
    if (!cropArea) return;

    const handleWheel = (event: WheelEvent) => {
      if (event.deltaY === 0) return;
      event.preventDefault();
      const zoomDelta = event.deltaY < 0 ? 0.1 : -0.1;
      setZoom((current) => Number(clampZoom(current + zoomDelta).toFixed(2)));
    };

    cropArea.addEventListener("wheel", handleWheel, { passive: false });
    return () => cropArea.removeEventListener("wheel", handleWheel);
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit(Math.round(positionX), Math.round(positionY), Number(zoom.toFixed(2)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the thumbnail.");
      setSubmitting(false);
    }
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    pointerRef.current = { x: event.clientX, y: event.clientY };
    setDragging(true);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const previous = pointerRef.current;
    if (!previous) return;

    const frame = event.currentTarget.getBoundingClientRect();
    const deltaX = event.clientX - previous.x;
    const deltaY = event.clientY - previous.y;
    const sensitivity = 100 / zoom;

    setPositionX((current) => clamp(current - (deltaX / frame.width) * sensitivity));
    setPositionY((current) => clamp(current - (deltaY / frame.height) * sensitivity));
    pointerRef.current = { x: event.clientX, y: event.clientY };
  };

  const finishDragging = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    pointerRef.current = null;
    setDragging(false);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 5 : 1;
    if (event.key === "+" || event.key === "=") {
      setZoom((current) => Number(clampZoom(current + 0.1).toFixed(2)));
    } else if (event.key === "-") {
      setZoom((current) => Number(clampZoom(current - 0.1).toFixed(2)));
    } else if (event.key === "ArrowLeft") setPositionX((current) => clamp(current + step));
    else if (event.key === "ArrowRight") setPositionX((current) => clamp(current - step));
    else if (event.key === "ArrowUp") setPositionY((current) => clamp(current + step));
    else if (event.key === "ArrowDown") setPositionY((current) => clamp(current - step));
    else return;
    event.preventDefault();
  };

  const resetCrop = () => {
    setPositionX(50);
    setPositionY(50);
    setZoom(1);
  };

  const imageStyle = {
    objectPosition: `${positionX}% ${positionY}%`,
    transformOrigin: `${positionX}% ${positionY}%`,
    transform: `scale(${zoom})`,
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div
        ref={cropAreaRef}
        role="group"
        aria-label="Thumbnail crop area"
        tabIndex={0}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishDragging}
        onPointerCancel={finishDragging}
        onKeyDown={handleKeyDown}
        className={`relative mx-auto aspect-[5/2] w-full max-w-md touch-none select-none overflow-hidden rounded-lg bg-slate-100 ring-1 ring-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 ${
          dragging ? "cursor-grabbing" : "cursor-grab"
        }`}
      >
        <img
          src={pet.photo_url ?? ""}
          alt={`${pet.name} thumbnail preview`}
          draggable={false}
          className="pointer-events-none h-full w-full object-cover"
          style={imageStyle}
        />
        <div
          aria-hidden="true"
          className={`pointer-events-none absolute inset-0 transition-opacity ${
            dragging ? "opacity-100" : "opacity-0"
          }`}
        >
          <span className="absolute inset-y-0 left-1/3 border-l border-white/70" />
          <span className="absolute inset-y-0 left-2/3 border-l border-white/70" />
          <span className="absolute inset-x-0 top-1/3 border-t border-white/70" />
          <span className="absolute inset-x-0 top-2/3 border-t border-white/70" />
        </div>
      </div>

      {error && (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <Button type="button" variant="ghost" onClick={resetCrop}>
          Reset
        </Button>
        <div className="flex gap-3">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Save thumbnail
          </Button>
        </div>
      </div>
    </form>
  );
}
