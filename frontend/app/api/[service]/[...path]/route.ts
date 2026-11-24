/**
 * Same-origin proxy from the browser to the internal services.
 *
 *   /api/backend/<path>  ->  AMLENS_BACKEND_URL/<path>
 *   /api/rag/<path>      ->  AMLENS_RAG_URL/<path>
 *
 * Why: in a deployment only this frontend is public (behind Entra ID sign-in via
 * Azure Container Apps authentication); the backend and RAG have internal ingress.
 * The URLs are read at request time, so one image works in every environment
 * (NEXT_PUBLIC_* values would be frozen into the bundle at build time), and the
 * browser never needs CORS.
 *
 * Every forwarded request carries AMLENS_PROXY_KEY (the backend rejects calls
 * without it when its AML_PROXY_KEY is set) and the signed-in user's name from
 * Easy Auth's X-MS-CLIENT-PRINCIPAL-NAME header (Easy Auth sets this header
 * itself and drops any copy sent by the client).
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const upstreams: Record<string, string | undefined> = {
  backend: process.env.AMLENS_BACKEND_URL,
  rag: process.env.AMLENS_RAG_URL,
};

// Request headers worth forwarding; everything else (cookies, Easy Auth tokens) stays here.
const FORWARD_REQUEST = ["accept", "content-type"];
const FORWARD_RESPONSE = ["content-type", "content-disposition", "cache-control"];

async function proxy(request: NextRequest, { params }: { params: { service: string; path: string[] } }) {
  const base = upstreams[params.service];
  if (!base) {
    return Response.json({ detail: `Service '${params.service}' is not configured on this server.` }, { status: 404 });
  }
  // Re-encode each segment so "..", "/" or "?" inside a segment cannot escape the upstream path.
  const path = params.path.map(encodeURIComponent).join("/");
  const target = `${base.replace(/\/$/, "")}/${path}${request.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const key = process.env.AMLENS_PROXY_KEY;
  if (key) headers.set("x-amlens-proxy-key", key);
  const user = request.headers.get("x-ms-client-principal-name");
  if (user) headers.set("x-amlens-user", user);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return Response.json({ detail: `The ${params.service} service is unreachable.` }, { status: 502 });
  }

  const responseHeaders = new Headers();
  for (const name of FORWARD_RESPONSE) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
