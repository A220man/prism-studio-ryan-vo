import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

vi.mock("./api/client", () => ({
  api: {
    health: vi.fn().mockResolvedValue({
      status: "healthy",
      app: "Prism Studio",
      version: "1.0.0",
      database: "connected",
    }),
  },
}));

describe("App", () => {
  it("shows loading state initially", async () => {
    render(<App />);
    expect(screen.getByText("Loading...")).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText("Loading...")).toBeNull();
    });
  });
});