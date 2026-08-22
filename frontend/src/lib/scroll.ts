/*
 * Scrolling that is allowed to be pretty but has to be correct.
 *
 * Two things make the naive call wrong here.
 *
 * `scrollIntoView({ behavior: "smooth" })` is a request, not a guarantee. It is
 * a no-op wherever smooth scrolling is switched off — an OS "reduce motion"
 * setting, some embedded and automated browsers, a few enterprise policies —
 * and it fails silently, leaving the page exactly where it was. That is fine
 * for a decorative scroll and not fine here: the whole point of moving the page
 * is that an owner should be looking at "contact a vet now" and the button that
 * finds one, so a scroll that quietly does nothing puts us back at the bug we
 * were fixing.
 *
 * And the app has a sticky header. `block: "start"` aligns an element with the
 * top of the VIEWPORT, which is underneath that header — so a focused step
 * heading landed behind it and the owner saw the questions without the question
 * they belonged to. Every position here is measured from the bottom of the
 * header instead, and "is it visible" means visible below the header, not
 * merely inside the viewport.
 */

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true
  );
}

type Block = "start" | "center" | "nearest";

/** Breathing room between the header and whatever we scrolled to. */
const GAP = 12;

/*
 * How much of the top of the viewport is spoken for.
 *
 * Measured rather than hard-coded: the header is one row on a phone and a
 * taller row with navigation on a desktop, and a restriction banner can sit
 * under it for some accounts. A fixed 64px would be wrong in two of those three
 * cases. Only sticky and fixed elements count — a header that scrolls away is
 * not covering anything by the time we arrive.
 */
export function stickyHeaderOffset(): number {
  if (typeof document === "undefined") return 0;
  let offset = 0;
  for (const element of document.querySelectorAll("header")) {
    const style = window.getComputedStyle(element);
    if (style.position !== "sticky" && style.position !== "fixed") continue;
    offset = Math.max(offset, element.getBoundingClientRect().bottom);
  }
  return Math.max(0, offset);
}

/** Visible to a reader — inside the viewport AND out from under the header. */
export function isVisibleBelowHeader(element: Element): boolean {
  const rect = element.getBoundingClientRect();
  const top = stickyHeaderOffset();
  return rect.top >= top && rect.bottom <= window.innerHeight;
}

function targetScrollTop(element: Element, block: Block): number | null {
  const rect = element.getBoundingClientRect();
  const headerBottom = stickyHeaderOffset();
  const usable = window.innerHeight - headerBottom;
  const documentTop = rect.top + window.scrollY;

  if (block === "nearest" && isVisibleBelowHeader(element)) return null;

  if (block === "center" && rect.height < usable) {
    return documentTop - headerBottom - (usable - rect.height) / 2;
  }
  // "start", and anything taller than the space available: put its top just
  // below the header, which is the most of it we can show.
  return documentTop - headerBottom - GAP;
}

export function scrollIntoViewSafely(element: Element | null, block: Block = "start"): void {
  if (!element || typeof window === "undefined") return;

  const target = targetScrollTop(element, block);
  if (target === null) return; // Already where it needs to be.

  const top = Math.max(0, Math.round(target));
  const smooth = !prefersReducedMotion();
  window.scrollTo({ top, behavior: smooth ? "smooth" : "auto" });
  if (!smooth) return;

  /*
   * Checked on a timer rather than on an animation frame. A smooth scroll is
   * driven by the rendering loop, and so is requestAnimationFrame — so in every
   * case where the smooth scroll does not run (a hidden or backgrounded tab,
   * smooth scrolling switched off), an rAF fallback does not run either, which
   * is precisely backwards. A timeout fires in all of them.
   *
   * 350ms is longer than a browser's smooth scroll and short enough that a
   * correction is not perceived as a second jump.
   */
  window.setTimeout(() => {
    if (!isVisibleBelowHeader(element)) window.scrollTo({ top, behavior: "auto" });
  }, 350);
}
