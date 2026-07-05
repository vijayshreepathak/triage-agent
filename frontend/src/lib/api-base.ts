/** Resolve backend base URL — direct in production, /engine proxy locally. */
export function resolveApiBase(): string {
  const direct = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (direct) {
    let url = direct.replace(/\/+$/, "");
    if (url.endsWith("/api")) url = url.slice(0, -4);
    return url;
  }
  return "/engine";
}

export function resolveApiPath(path: string): string {
  const base = resolveApiBase();
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalized}`;
}
