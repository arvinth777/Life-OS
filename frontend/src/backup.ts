import { api, base } from "./api";

async function sha256(bytes: ArrayBuffer) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
}

async function chunk(path: string, body?: Blob) {
  const response = await fetch(base + "/api" + path, {
    method: body ? "POST" : "GET",
    headers: {
      Authorization: "Bearer " + sessionStorage.getItem("life-os-token"),
      "Content-Type": "application/octet-stream",
    },
    body,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Backup transfer failed. Please try again.");
  }
  return response;
}

export async function downloadBackup() {
  const transfer = await api("/transfers/download", "POST");
  try {
    const parts: ArrayBuffer[] = [];
    for (let i = 0; i < transfer.count; i++) {
      parts.push(await (await chunk(`/transfers/${transfer.id}/chunks/${i}`)).arrayBuffer());
    }
    const result = new Blob(parts, { type: "application/zip" });
    if (result.size !== transfer.size || await sha256(await result.arrayBuffer()) !== transfer.sha256) {
      throw new Error("Backup checksum failed. Please download again.");
    }
    return result;
  } finally {
    await api(`/transfers/${transfer.id}`, "DELETE").catch(() => {});
  }
}

export async function restoreBackup(file: File) {
  if (file.size === 0 || file.size > 25_000_000) throw new Error("Choose a backup up to 25 MB.");
  const transfer = await api("/transfers/upload", "POST", {
    size: file.size, sha256: await sha256(await file.arrayBuffer()),
  });
  let restored = false;
  try {
    for (let i = 0; i < transfer.count; i++) {
      await chunk(`/transfers/${transfer.id}/chunks/${i}`, file.slice(i * transfer.chunk_size, (i + 1) * transfer.chunk_size));
    }
    await api(`/transfers/${transfer.id}/restore?replace=true`, "POST");
    restored = true;
  } finally {
    if (!restored) await api(`/transfers/${transfer.id}`, "DELETE").catch(() => {});
  }
}
