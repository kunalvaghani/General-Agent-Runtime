import { it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Models, Memory, SettingsForm } from "../components/management";
afterEach(()=>vi.unstubAllGlobals());
it("surfaces model discovery failures and retries",async()=>{
  const fetch=vi.fn().mockRejectedValueOnce(new Error("Ollama unavailable")).mockResolvedValue({ok:true,json:async()=>[{id:"local",provider:"ollama"}]});vi.stubGlobal("fetch",fetch);
  render(<Models/>);await screen.findByText("Ollama unavailable");fireEvent.click(screen.getByText("Refresh models"));await screen.findByText("local");
});
it("validates settings and preserves inputs when save fails",async()=>{
  const fetch=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({default_model:"local",model_timeout:120})}).mockRejectedValueOnce(new Error("Disk full"));vi.stubGlobal("fetch",fetch);
  render(<SettingsForm/>);await screen.findByLabelText("Default model");
  fireEvent.change(screen.getByLabelText("Model timeout (seconds)"),{target:{value:"0"}});fireEvent.click(screen.getByText("Save settings"));await screen.findByText(/Timeout must/);expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("Model timeout (seconds)"),{target:{value:"60"}});fireEvent.click(screen.getByText("Save settings"));await screen.findByText("Disk full");expect(screen.getByLabelText("Default model")).toHaveValue("local");
});
it("requires explicit deletion and refreshes memory after deletion",async()=>{
  const item={id:"one",type:"episodic",content:"Test evidence",source_task_id:"source",importance:0.8,created_at:1,expires_at:null};
  const fetch=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>[item]}).mockResolvedValueOnce({ok:true,json:async()=>({deleted:true})}).mockResolvedValue({ok:true,json:async()=>[]});vi.stubGlobal("fetch",fetch);
  render(<Memory/>);await screen.findByText("Test evidence");fireEvent.click(screen.getByText("Remove"));expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText("Delete memory"));await waitFor(()=>expect(screen.queryByText("Test evidence")).not.toBeInTheDocument());
  expect(fetch.mock.calls[1][1].method).toBe("DELETE");
});

