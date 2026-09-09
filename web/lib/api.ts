export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const base = process.env.NEXT_PUBLIC_GAR_API_URL || "/api/v1";
  const response = await fetch(`${base}${path}`, { ...init, headers: {
    "Content-Type": "application/json", ...init?.headers }, cache: "no-store", signal: init?.signal ?? AbortSignal.timeout(15000) });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof body.detail === "string" ? body.detail :
      `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
