const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function getBackendBaseUrl() {
  const value = process.env.EXTRUDER_BACKEND_URL || "";
  if (!value) {
    throw new Error("EXTRUDER_BACKEND_URL is not configured on Vercel.");
  }
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function getAuthHeader() {
  const username = process.env.EXTRUDER_BACKEND_USERNAME || "";
  const password = process.env.EXTRUDER_BACKEND_PASSWORD || "";
  if (!username || !password) {
    return null;
  }
  return `Basic ${Buffer.from(`${username}:${password}`, "utf8").toString("base64")}`;
}

function filterRequestHeaders(headers) {
  const outgoing = {};
  for (const [key, value] of Object.entries(headers || {})) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(lower) || lower === "authorization") {
      continue;
    }
    outgoing[key] = value;
  }
  return outgoing;
}

function copyResponseHeaders(sourceHeaders, target) {
  for (const [key, value] of sourceHeaders.entries()) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      continue;
    }
    target.setHeader(key, value);
  }
}

function extractPathSegments(req) {
  const value = req.query.path;
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string" && value.length > 0) {
    return [value];
  }
  return [];
}

export default async function handler(req, res) {
  try {
    const pathSegments = extractPathSegments(req);
    const upstreamPath = pathSegments.join("/");
    const backendBaseUrl = getBackendBaseUrl();
    const upstreamUrl = new URL(`${backendBaseUrl}/api/${upstreamPath}`);

    for (const [key, value] of Object.entries(req.query || {})) {
      if (key === "path") {
        continue;
      }
      if (Array.isArray(value)) {
        for (const item of value) {
          upstreamUrl.searchParams.append(key, String(item));
        }
      } else if (value !== undefined) {
        upstreamUrl.searchParams.set(key, String(value));
      }
    }

    const headers = filterRequestHeaders(req.headers);
    const authHeader = getAuthHeader();
    if (authHeader) {
      headers.Authorization = authHeader;
    }

    const method = req.method || "GET";
    const shouldSendBody = !["GET", "HEAD"].includes(method.toUpperCase());
    const upstreamResponse = await fetch(upstreamUrl, {
      method,
      headers,
      body: shouldSendBody ? JSON.stringify(req.body) : undefined,
    });

    copyResponseHeaders(upstreamResponse.headers, res);
    res.status(upstreamResponse.status);

    const contentType = upstreamResponse.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await upstreamResponse.json();
      res.json(data);
      return;
    }

    const text = await upstreamResponse.text();
    res.send(text);
  } catch (error) {
    res.status(502).json({
      detail: error instanceof Error ? error.message : "Vercel proxy request failed.",
    });
  }
}
