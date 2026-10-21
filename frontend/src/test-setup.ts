import { vi } from "vitest";
import "@testing-library/jest-dom";

declare const globalThis: {
  vi?: typeof vi;
};

globalThis.vi = vi;