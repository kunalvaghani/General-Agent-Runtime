import { describe, it, expect, vi } from "vitest";
import { api } from "../lib/api";
describe("API errors", () => { it("preserves backend validation errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:"Stale approval"})}));
  await expect(api("/tasks/x/approve")).rejects.toThrow("Stale approval"); vi.unstubAllGlobals();
}); });
