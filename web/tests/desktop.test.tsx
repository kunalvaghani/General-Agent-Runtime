import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Desktop } from "../components/desktop";
import { api } from "../lib/api";
vi.mock("../lib/api",()=>({api:vi.fn()}));
beforeEach(()=>vi.mocked(api).mockReset());
const record={id:"a".repeat(32),state:"awaiting_approval",entry:"app.py",workspace:"task workspace",image:"sha256:tested",files:{"app.py":"digest"},test_output:"1 passed"};
it("explains a task ID cannot attach a desktop session",()=>{
  render(<Desktop taskId="t" verified={false}/>);
  fireEvent.change(screen.getByLabelText("Desktop session ID"),{target:{value:"t"}});
  fireEvent.click(screen.getByRole("button",{name:"Attach"}));
  expect(screen.getByRole("alert")).toHaveTextContent("This is the task ID");
  expect(api).not.toHaveBeenCalled();
});
it("keeps desktop testing disabled until task verification passes",()=>{
  render(<Desktop taskId="t" verified={false}/>);
  expect(screen.getByRole("button",{name:"Test frozen copy"})).toBeDisabled();
  expect(api).not.toHaveBeenCalled();
});
it("requires a separate reviewed approval after snapshot tests",async()=>{
  vi.mocked(api).mockResolvedValueOnce(record).mockResolvedValueOnce({...record,state:"stopped"});
  render(<Desktop taskId="t" verified/>);
  fireEvent.click(screen.getByRole("button",{name:"Test frozen copy"}));
  await screen.findByText("Tests passed — approve desktop launch?");
  expect(api).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/No host shell, network, or clipboard sharing/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"Approve and open isolated desktop"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith(`/tasks/t/desktop/${record.id}/approve`,{method:"POST"}));
});
it("never offers launch approval when frozen-copy tests fail",async()=>{
  vi.mocked(api).mockRejectedValueOnce(new Error("2 failed"));
  render(<Desktop taskId="t" verified/>);
  fireEvent.click(screen.getByRole("button",{name:"Test frozen copy"}));
  await screen.findByRole("alert");
  expect(screen.queryByRole("button",{name:"Approve and open isolated desktop"})).toBeNull();
});
