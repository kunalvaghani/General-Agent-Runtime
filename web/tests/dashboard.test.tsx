import { render, screen, fireEvent } from "@testing-library/react";
import { it, expect, vi } from "vitest";
import { Dashboard } from "../components/dashboard";
import { examples } from "./fixtures/tasks";
it("filters real task links and shows connected state after loading", async () => {
  render(<Dashboard load={async () => examples}/>);
  await screen.findByText("API · CONNECTED");
  fireEvent.change(screen.getByLabelText("Status"), {target:{value:"BLOCKED"}});
  expect(screen.getByRole("link", {name:/Inspect an unavailable/})).toHaveAttribute("href","/tasks/example-blocked");
  expect(screen.queryByText("Add tests for the workspace parser")).not.toBeInTheDocument();
});
it("shows empty and recoverable load errors", async () => {
  const load = vi.fn().mockRejectedValueOnce(new Error("API unavailable")).mockResolvedValue([]);
  render(<Dashboard load={load}/>);
  await screen.findByText("API unavailable", {exact:false});
  fireEvent.click(screen.getByText("Retry"));
  await screen.findByText("No tasks match this view.");
});

