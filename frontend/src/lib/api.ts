// One small wrapper around fetch: adds the login token, sends JSON, and turns API errors into
// exceptions with the server's own message ("Wrong email or password.").

const TOKEN_KEY = "spendwise.token";

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* private mode: stay logged in for this tab only */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Options = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { json, ...init } = options;
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = init.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  const res = await fetch(path, { ...init, headers, body });
  if (res.status === 401 && token) {
    tokenStore.clear();
    window.dispatchEvent(new Event("spendwise:logout")); // the token expired: back to the login page
  }
  if (!res.ok) {
    let message = res.statusText || "Something went wrong";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d: { msg: string }) => d.msg).join(", ");
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (res.headers.get("content-type") ?? "").includes("json") ? res.json() : ((await res.text()) as T);
}

/** Downloads a file from an authenticated endpoint (a plain <a href> can't send the token). */
export async function download(path: string, filename: string) {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${tokenStore.get() ?? ""}` } });
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
