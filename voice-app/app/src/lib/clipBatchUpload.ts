/**
 * Concurrency-limited fan-out for importing a batch of clips.
 *
 * One request per file, so every check the single-clip path already performs (size,
 * duration, container, ffprobe) applies unchanged and a rejected file costs only itself.
 * A partially loaded batch is more useful than an all-or-nothing one, so there is no
 * rollback: whatever loaded stays loaded and the caller reports the failures.
 */

export interface ClipBatchUploadOutcome<TEntry, TClip> {
  succeeded: Array<TEntry & { clip: TClip }>;
  failed: Array<TEntry & { message: string }>;
  total: number;
}

export interface ClipBatchUploadOptions {
  /** Requests in flight at once. The backend runs ffprobe per file, so this stays small. */
  concurrency?: number;
  onProgress?: (done: number, total: number) => void;
}

const DEFAULT_CONCURRENCY = 4;

export async function runClipBatchUpload<TEntry, TClip>(
  entries: readonly TEntry[],
  uploadOne: (entry: TEntry) => Promise<TClip>,
  options: ClipBatchUploadOptions = {},
): Promise<ClipBatchUploadOutcome<TEntry, TClip>> {
  const total = entries.length;
  // Outcomes are parked by index so the report reads in the caller's order (segment order)
  // rather than in whatever order the requests happened to finish.
  const outcomes = new Array<
    { ok: true; clip: TClip } | { ok: false; message: string } | undefined
  >(total);
  let done = 0;
  let cursor = 0;

  const worker = async () => {
    while (cursor < total) {
      const index = cursor++;
      try {
        outcomes[index] = { ok: true, clip: await uploadOne(entries[index]) };
      } catch (error) {
        outcomes[index] = {
          ok: false,
          message: error instanceof Error ? error.message : String(error),
        };
      }
      done += 1;
      options.onProgress?.(done, total);
    }
  };

  const lanes = Math.max(1, Math.min(options.concurrency ?? DEFAULT_CONCURRENCY, total || 1));
  await Promise.all(Array.from({ length: lanes }, () => worker()));

  const succeeded: Array<TEntry & { clip: TClip }> = [];
  const failed: Array<TEntry & { message: string }> = [];
  entries.forEach((entry, index) => {
    const outcome = outcomes[index];
    if (outcome === undefined) return;
    if (outcome.ok) {
      succeeded.push({ ...entry, clip: outcome.clip });
    } else {
      failed.push({ ...entry, message: outcome.message });
    }
  });
  return { succeeded, failed, total };
}
