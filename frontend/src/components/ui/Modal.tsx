import { useEffect } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { XIcon } from "./icons";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Rendered right-aligned below the content, typically Buttons. */
  footer?: ReactNode;
}

export default function Modal({ open, onClose, title, children, footer }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        /*
          A column with a ceiling, so a dialog taller than the window stays
          inside it. Without the ceiling the panel simply grew: the overlay is
          `fixed inset-0`, so the page behind cannot scroll, and the parts that
          overflowed - the title at the top and the submit button at the bottom
          - were unreachable by any means. A form only has to gain a couple of
          lines to cross that threshold, and one did.

          `dvh` rather than `vh` because a phone's address bar is part of `vh`
          and not part of what you can actually see.
        */
        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-lg flex-col rounded-2xl bg-white p-6 shadow-xl"
      >
        <div className="flex shrink-0 items-start justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>
        {/*
          Only the content scrolls. Scrolling the whole dialog would take the
          title and the buttons off the screen with it, and the buttons are the
          reason the dialog is open.

          `min-h-0` because a flex child defaults to `min-height: auto`, which
          refuses to shrink below its content and would defeat the ceiling
          above. The negative margin plus matching padding gives focus rings
          room inside the scroll box instead of clipping them.
        */}
        <div className="-mx-1 mt-4 min-h-0 flex-1 overflow-y-auto px-1">{children}</div>
        {footer && <div className="mt-6 flex shrink-0 justify-end gap-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
