import { constants } from "node:fs";
import { lstat, open, realpath } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";

export class StableFileError extends Error {
  constructor(code) {
    super(code);
    this.name = "StableFileError";
    this.code = code;
  }
}

function normalizedPath(value) {
  const resolved = path.resolve(value);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function confined(file, root) {
  if (!root) return true;
  const relative = path.relative(path.resolve(root), path.resolve(file));
  return relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function identity(stat) {
  return [stat.dev, stat.ino, stat.size, stat.mtimeNs, stat.ctimeNs].map(String).join(":");
}

async function openStable(file, { root = null, maxBytes }) {
  const requested = path.resolve(file);
  if (!confined(requested, root)) throw new StableFileError("file_outside_allowed_root");
  const link = await lstat(requested, { bigint: true });
  if (!link.isFile() || link.isSymbolicLink()) throw new StableFileError("file_not_regular_or_reparse");
  const canonical = await realpath(requested);
  if (normalizedPath(canonical) !== normalizedPath(requested)) throw new StableFileError("file_reparse_resolution_changed");
  const flags = constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0);
  const handle = await open(requested, flags);
  try {
    const before = await handle.stat({ bigint: true });
    if (!before.isFile()) throw new StableFileError("opened_file_not_regular");
    if (identity(before) !== identity(link)) throw new StableFileError("file_identity_changed_before_open");
    if (before.size > BigInt(maxBytes)) throw new StableFileError("file_size_limit_exceeded");
    return { requested, handle, before, beforeIdentity: identity(before) };
  } catch (error) {
    await handle.close();
    throw error;
  }
}

async function finishStable(opened) {
  const after = await opened.handle.stat({ bigint: true });
  if (identity(after) !== opened.beforeIdentity) throw new StableFileError("file_identity_changed_during_read");
}

export async function readStableFile(file, options = {}) {
  const opened = await openStable(file, { root: options.root, maxBytes: options.maxBytes ?? 4 * 1024 * 1024 });
  try {
    const bytes = await opened.handle.readFile();
    await finishStable(opened);
    return { bytes, sha256: createHash("sha256").update(bytes).digest("hex"), identity: opened.beforeIdentity };
  } finally {
    await opened.handle.close();
  }
}

export async function hashStableFile(file, options = {}) {
  const opened = await openStable(file, { root: options.root, maxBytes: options.maxBytes ?? 32 * 1024 * 1024 * 1024 });
  try {
    const digest = createHash("sha256");
    const stream = opened.handle.createReadStream({ autoClose: false, start: 0 });
    for await (const chunk of stream) digest.update(chunk);
    await finishStable(opened);
    return { sha256: digest.digest("hex"), identity: opened.beforeIdentity, size: Number(opened.before.size) };
  } finally {
    await opened.handle.close();
  }
}
