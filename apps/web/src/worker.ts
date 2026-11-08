type AssetsBinding = {
  fetch(request: Request): Promise<Response>;
};

type WorkerEnv = {
  API_ORIGIN: string;
  ASSETS: AssetsBinding;
};

type Fetcher = (input: string | URL, init?: RequestInit) => Promise<Response>;

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

const SPOOFABLE_HEADERS = new Set([
  "host",
  "forwarded",
  "x-forwarded-for",
  "x-forwarded-host",
  "x-forwarded-proto",
  "x-forwarded-port",
  "x-forwarded-server",
  "x-real-ip",
]);

function connectionHeaderNames(headers: Headers): Set<string> {
  return new Set(
    (headers.get("connection") ?? "")
      .split(",")
      .map((name) => name.trim().toLowerCase())
      .filter(Boolean),
  );
}

function copySafeHeaders(source: Headers, response = false): Headers {
  const blocked = connectionHeaderNames(source);
  for (const name of HOP_BY_HOP_HEADERS) blocked.add(name);
  if (!response) {
    for (const name of SPOOFABLE_HEADERS) blocked.add(name);
  }

  const result = new Headers();
  const getSetCookie = (source as Headers & { getSetCookie?: () => string[] }).getSetCookie;
  const cookies = response && getSetCookie ? getSetCookie.call(source) : [];

  source.forEach((value, name) => {
    const normalized = name.toLowerCase();
    if (
      blocked.has(normalized) ||
      normalized.startsWith("x-kubanfy-internal-")
    ) {
      return;
    }
    if (response && normalized === "set-cookie" && cookies.length > 0) return;
    result.append(name, value);
  });

  for (const cookie of cookies) result.append("set-cookie", cookie);
  return result;
}

function getValidatedApiOrigin(value: string | undefined): URL {
  if (!value) throw new Error("Invalid API_ORIGIN");
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error("Invalid API_ORIGIN");
  }

  if (
    parsed.protocol !== "https:" ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash ||
    parsed.origin !== value
  ) {
    throw new Error("Invalid API_ORIGIN");
  }
  return parsed;
}

export async function proxyApiRequest(
  request: Request,
  env: Pick<WorkerEnv, "API_ORIGIN">,
  fetcher: Fetcher = fetch,
): Promise<Response> {
  const origin = getValidatedApiOrigin(env.API_ORIGIN);
  const incoming = new URL(request.url);
  const upstream = new URL(origin.origin);
  upstream.pathname = incoming.pathname.slice("/api".length) || "/";
  upstream.search = incoming.search;

  const headers = copySafeHeaders(request.headers);
  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  const upstreamResponse = await fetcher(upstream, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    redirect: "manual",
  });

  const responseHeaders = copySafeHeaders(upstreamResponse.headers, true);
  const body =
    request.method === "HEAD" ||
    upstreamResponse.status === 204 ||
    upstreamResponse.status === 205 ||
    upstreamResponse.status === 304
      ? null
      : upstreamResponse.body;

  return new Response(body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  });
}

export async function handleRequest(
  request: Request,
  env: WorkerEnv,
  fetcher: Fetcher = fetch,
): Promise<Response> {
  const pathname = new URL(request.url).pathname;
  if (!pathname.startsWith("/api/")) {
    return env.ASSETS.fetch(request);
  }

  try {
    return await proxyApiRequest(request, env, fetcher);
  } catch {
    return new Response(JSON.stringify({ detail: "API proxy is not configured" }), {
      status: 502,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  }
}

export default {
  fetch(request: Request, env: WorkerEnv): Promise<Response> {
    return handleRequest(request, env);
  },
};
