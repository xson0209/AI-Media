/**
 * Matching of user-picked clip files to shots by filename.
 *
 * Google Flow does not let the user name the files it downloads, so the agreed
 * convention is that the user renames each clip to its segment number (`1.mp4`,
 * `2.mp4`, ...). Only a filename whose stem is entirely digits is matched; nothing
 * is inferred from FileList order, file mtime, or video content, because a browser
 * gives no guarantee that FileList order matches what the user saw, and an OS sort
 * puts `10.mp4` right after `1.mp4`.
 */

export type ClipBatchSkipReason =
  | 'not_a_number'
  | 'no_such_segment'
  | 'duplicate_segment';

export interface ClipBatchShot {
  id: string;
  shot_order: number;
}

export interface ClipBatchMatched<TFile, TShot extends ClipBatchShot> {
  file: TFile;
  filename: string;
  shot: TShot;
  shotOrder: number;
  /** True when the shot already holds an active clip that this file will replace. */
  replacesExistingClip: boolean;
}

export interface ClipBatchSkipped<TFile> {
  file: TFile;
  filename: string;
  reason: ClipBatchSkipReason;
  /** Parsed segment number, when the stem was numeric but unusable. */
  shotOrder?: number;
}

export interface ClipBatchPlan<TFile, TShot extends ClipBatchShot> {
  matched: ClipBatchMatched<TFile, TShot>[];
  skipped: ClipBatchSkipped<TFile>[];
}

/** Filename stems that are entirely digits, so `007.mp4` and `7.mp4` mean segment 7. */
const NUMERIC_STEM = /^\d+$/;

/**
 * Read the segment number out of a filename.
 *
 * Returns null when the stem is not purely numeric, or parses to zero — segment
 * numbering starts at 1, so `0.mp4` names no segment. A leading `-` never reaches
 * the number branch because it fails NUMERIC_STEM, which is what we want: a negative
 * segment is a naming mistake, not a segment.
 */
export function segmentNumberFromFilename(filename: string): number | null {
  const name = String(filename ?? '');
  const lastDot = name.lastIndexOf('.');
  // A leading dot is part of the name (".mp4" has no stem), so only split on a dot
  // that has something before it.
  const stem = lastDot > 0 ? name.slice(0, lastDot) : name;
  if (!NUMERIC_STEM.test(stem)) return null;
  const parsed = Number.parseInt(stem, 10);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) return null;
  return parsed;
}

export function clipBatchSkipReasonLabel(reason: ClipBatchSkipReason): string {
  switch (reason) {
    case 'not_a_number':
      return 'Tên file không phải số thứ tự phân đoạn';
    case 'no_such_segment':
      return 'Không có phân đoạn tương ứng trong dự án';
    case 'duplicate_segment':
      return 'Nhiều file cùng trỏ về một phân đoạn';
  }
}

/**
 * Build the match table shown to the user before anything is uploaded.
 *
 * When two files claim the same segment neither is matched: the user renamed
 * something wrong, and picking one for them would silently discard a clip they
 * meant to import.
 */
export function buildClipBatchPlan<TFile extends { name: string }, TShot extends ClipBatchShot>(
  files: readonly TFile[],
  shots: readonly TShot[],
  options: { shotIdsWithClip?: ReadonlySet<string> } = {},
): ClipBatchPlan<TFile, TShot> {
  const shotByOrder = new Map<number, TShot>();
  for (const shot of shots) {
    shotByOrder.set(shot.shot_order, shot);
  }

  const parsed = files.map((file) => ({
    file,
    filename: file.name,
    shotOrder: segmentNumberFromFilename(file.name),
  }));

  // Count first so that both sides of a collision can be reported, not just the second.
  const claimCount = new Map<number, number>();
  for (const entry of parsed) {
    if (entry.shotOrder === null) continue;
    if (!shotByOrder.has(entry.shotOrder)) continue;
    claimCount.set(entry.shotOrder, (claimCount.get(entry.shotOrder) ?? 0) + 1);
  }

  const matched: ClipBatchMatched<TFile, TShot>[] = [];
  const skipped: ClipBatchSkipped<TFile>[] = [];
  const shotIdsWithClip = options.shotIdsWithClip ?? new Set<string>();

  for (const entry of parsed) {
    if (entry.shotOrder === null) {
      skipped.push({ file: entry.file, filename: entry.filename, reason: 'not_a_number' });
      continue;
    }
    const shot = shotByOrder.get(entry.shotOrder);
    if (shot === undefined) {
      skipped.push({
        file: entry.file,
        filename: entry.filename,
        reason: 'no_such_segment',
        shotOrder: entry.shotOrder,
      });
      continue;
    }
    if ((claimCount.get(entry.shotOrder) ?? 0) > 1) {
      skipped.push({
        file: entry.file,
        filename: entry.filename,
        reason: 'duplicate_segment',
        shotOrder: entry.shotOrder,
      });
      continue;
    }
    matched.push({
      file: entry.file,
      filename: entry.filename,
      shot,
      shotOrder: entry.shotOrder,
      replacesExistingClip: shotIdsWithClip.has(shot.id),
    });
  }

  matched.sort((left, right) => left.shotOrder - right.shotOrder);
  return { matched, skipped };
}
