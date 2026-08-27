import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// React Testing Library leaves its container in the document between tests
// unless something removes it, and a second render of the same page would then
// match two of every element.
afterEach(() => cleanup());
