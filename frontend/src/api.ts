export let base =
  import.meta.env.VITE_API_URL || localStorage.getItem("life-os-api") || "";
export function setBase(value: string) {
  base = value.replace(/\/$/, "");
  localStorage.setItem("life-os-api", base);
}
export async function api(path: string, method = "GET", body?: any) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(base + "/api" + path, {
      method,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization:
          "Bearer " + (sessionStorage.getItem("life-os-token") || ""),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const data = await response
        .json()
        .catch(() => ({ detail: "The API could not respond." }));
      if (response.status === 401 && path != "/auth/login")
        window.dispatchEvent(new Event("signed-out"));
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail),
      );
    }
    return response.json();
  } catch (e) {
    if (e instanceof TypeError)
      throw new Error(
        "Cannot reach your Life OS API. It may be waking up. Check its address and try again.",
      );
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}
export const title = (s: string) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
export let userZone = "UTC";
export function setZone(zone: string) {
  userZone = zone;
}
export const todayDate = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: userZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export const fmt = (value: any) =>
  value
    ? new Intl.DateTimeFormat(undefined, {
        timeZone: userZone,
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(new Date(value))
    : "No due date";
export const localInput = (iso?: string) => {
  const d = iso ? new Date(iso) : new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
