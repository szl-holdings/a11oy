import { QueryClient, QueryFunction } from "@tanstack/react-query";

const PUBLIC_API_ROOT = import.meta.env.VITE_OBSERVATORY_API_ROOT || "";
const API_BASE = PUBLIC_API_ROOT ? "" : ("__PORT_5000__".startsWith("__") ? "" : "__PORT_5000__");
if (PUBLIC_API_ROOT && !/^\/api\/a11oy\/v1\/civilian$/.test(PUBLIC_API_ROOT)) {
  throw new Error("Unsupported observatory API namespace");
}
const endpoint = (url: string) => `${API_BASE}${PUBLIC_API_ROOT ? PUBLIC_API_ROOT + url.replace(/^\/api(?=\/)/, "") : url}`;

async function throwIfResNotOk(res: Response) {
  if (!res.ok) {
    const text = (await res.text()) || res.statusText;
    throw new Error(`${res.status}: ${text}`);
  }
}

export async function apiRequest(
  method: string,
  url: string,
  data?: unknown | undefined,
): Promise<Response> {
  const res = await fetch(endpoint(url), {
    method,
    credentials: "same-origin",
    headers: data ? { "Content-Type": "application/json" } : {},
    body: data ? JSON.stringify(data) : undefined,
  });

  await throwIfResNotOk(res);
  return res;
}

type UnauthorizedBehavior = "returnNull" | "throw";
export const getQueryFn: <T>(options: {
  on401: UnauthorizedBehavior;
}) => QueryFunction<T> =
  ({ on401: unauthorizedBehavior }) =>
  async ({ queryKey }) => {
    const res = await fetch(endpoint(queryKey.join("/")), { credentials: "same-origin" });

    if (unauthorizedBehavior === "returnNull" && res.status === 401) {
      return null;
    }

    await throwIfResNotOk(res);
    return await res.json();
  };

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: getQueryFn({ on401: "throw" }),
      refetchInterval: false,
      refetchOnWindowFocus: false,
      staleTime: Infinity,
      retry: false,
    },
    mutations: {
      retry: false,
    },
  },
});
