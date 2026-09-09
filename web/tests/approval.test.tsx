import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Approval } from "../components/approval";
import { examples } from "./fixtures/tasks";
import { ApiError } from "../lib/api";
import { submitApproval } from "../lib/approval";
const pending=examples[0].metadata.execution!.pending!;
it.each([true,false])("submits the exact request once with approve=%s", async approve => {
  const submit=vi.fn().mockResolvedValue(undefined);
  render(<Approval taskId="t" pending={pending} submit={submit}/>);
  const button=screen.getByRole("button",{name:approve ? "Approve once" : "Reject"});
  fireEvent.click(button);fireEvent.click(button);
  await waitFor(()=>expect(screen.getByRole("status")).toHaveTextContent("Decision sent"));
  expect(submit).toHaveBeenCalledExactlyOnceWith({taskId:"t",requestId:pending.id,approve});
});
it("blocks stale approvals and provides refresh", async () => {
  const refresh=vi.fn();render(<Approval taskId="t" pending={pending} onRefresh={refresh}
    submit={async()=>{throw new ApiError(409,"stale");}}/>);
  fireEvent.click(screen.getByText("Approve once"));
  await waitFor(()=>expect(screen.getByRole("alert")).toHaveTextContent("already handled"));
  expect(screen.getByText("Reject")).toBeDisabled();fireEvent.click(screen.getByText("Refresh request"));
  expect(refresh).toHaveBeenCalledOnce();
});
it("keeps failed requests reviewable and retries after network failure", async () => {
  const submit=vi.fn().mockRejectedValueOnce(new Error("Offline")).mockResolvedValue(undefined);
  render(<Approval taskId="t" pending={pending} submit={submit}/>);
  fireEvent.click(screen.getByText("Approve once"));
  await waitFor(()=>expect(screen.getByRole("alert")).toHaveTextContent("Offline"));
  fireEvent.click(screen.getByText("Approve once"));
  await waitFor(()=>expect(screen.getByRole("status")).toHaveTextContent("Decision sent"));
});
it("sends only the backend approval contract, not editable tool arguments", async () => {
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({})});vi.stubGlobal("fetch",fetch);
  try {await submitApproval({taskId:"t",requestId:"exact-id",approve:false});
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({request_id:"exact-id",approve:false});
  } finally {vi.unstubAllGlobals();}
});

