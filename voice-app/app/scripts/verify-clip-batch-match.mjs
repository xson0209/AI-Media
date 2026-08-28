// Runs the real matching logic (not string assertions) against every skip reason and
// edge case named in the spec. Node >= 22.6 strips the TS types natively.
import { strict as assert } from 'node:assert';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
// On Windows a bare absolute path is not a valid ESM specifier; it must be a file:// URL.
const {
  buildClipBatchPlan,
  clipBatchSkipReasonLabel,
  segmentNumberFromFilename,
} = await import(pathToFileURL(join(root, 'src/lib/clipBatchMatch.ts')).href);

const shots = Array.from({ length: 18 }, (_, index) => ({
  id: `shot-${index + 1}`,
  shot_order: index + 1,
}));
const file = (name) => ({ name });

// --- segmentNumberFromFilename ---------------------------------------------------
assert.equal(segmentNumberFromFilename('1.mp4'), 1, 'plain number');
assert.equal(segmentNumberFromFilename('18.mp4'), 18, 'two digits');
assert.equal(segmentNumberFromFilename('03.mp4'), 3, 'leading zero reads as 3');
assert.equal(segmentNumberFromFilename('007.mov'), 7, 'multiple leading zeros');
assert.equal(segmentNumberFromFilename('intro.mp4'), null, 'non-numeric stem');
assert.equal(segmentNumberFromFilename('clip_2_v3.mp4'), null, 'mixed stem is not numeric');
assert.equal(segmentNumberFromFilename('0.mp4'), null, 'zero names no segment');
assert.equal(segmentNumberFromFilename('-1.mp4'), null, 'negative names no segment');
assert.equal(segmentNumberFromFilename('2.5.mp4'), null, 'dotted stem is not numeric');
assert.equal(segmentNumberFromFilename('5'), 5, 'no extension still reads');
assert.equal(segmentNumberFromFilename('.mp4'), null, 'leading dot has no stem');

// --- the happy path: 18 files named 1..18 ----------------------------------------
const full = buildClipBatchPlan(
  shots.map((shot) => file(`${shot.shot_order}.mp4`)),
  shots,
);
assert.equal(full.matched.length, 18, 'all 18 files match');
assert.equal(full.skipped.length, 0, 'nothing skipped');
for (const [index, entry] of full.matched.entries()) {
  assert.equal(entry.shotOrder, index + 1, 'matched in segment order');
  assert.equal(entry.shot.id, `shot-${index + 1}`, 'matched to the right shot');
  assert.equal(entry.replacesExistingClip, false, 'no existing clip by default');
}

// Matching must not depend on the order the files arrive in.
const shuffled = buildClipBatchPlan(
  ['10.mp4', '1.mp4', '18.mp4', '2.mp4'].map(file),
  shots,
);
assert.deepEqual(
  shuffled.matched.map((entry) => entry.shotOrder),
  [1, 2, 10, 18],
  'result is sorted by segment, not by input order',
);

// --- each skip reason ------------------------------------------------------------
const mixed = buildClipBatchPlan(
  ['1.mp4', 'intro.mp4', '19.mp4', '0.mp4'].map(file),
  shots,
);
assert.deepEqual(mixed.matched.map((entry) => entry.filename), ['1.mp4'], 'only the valid file matches');
const reasonByName = new Map(mixed.skipped.map((entry) => [entry.filename, entry.reason]));
assert.equal(reasonByName.get('intro.mp4'), 'not_a_number', 'non-numeric reason');
assert.equal(reasonByName.get('19.mp4'), 'no_such_segment', 'out-of-range reason');
assert.equal(reasonByName.get('0.mp4'), 'not_a_number', 'zero is not a segment number');

// --- duplicate segment: neither file wins ---------------------------------------
const duplicate = buildClipBatchPlan(['3.mp4', '03.mp4', '4.mp4'].map(file), shots);
assert.deepEqual(
  duplicate.matched.map((entry) => entry.filename),
  ['4.mp4'],
  'segment 3 imports nothing when two files claim it',
);
const dupSkips = duplicate.skipped.filter((entry) => entry.reason === 'duplicate_segment');
assert.equal(dupSkips.length, 2, 'BOTH sides of the collision are reported');
assert.deepEqual(
  dupSkips.map((entry) => entry.filename).sort(),
  ['03.mp4', '3.mp4'],
  'each colliding file is named',
);

// --- replacing an existing clip is flagged --------------------------------------
const replacing = buildClipBatchPlan(
  ['1.mp4', '2.mp4'].map(file),
  shots,
  { shotIdsWithClip: new Set(['shot-2']) },
);
assert.equal(replacing.matched[0].replacesExistingClip, false, 'segment 1 has no clip');
assert.equal(replacing.matched[1].replacesExistingClip, true, 'segment 2 replaces its clip');

// --- nothing matches -------------------------------------------------------------
const none = buildClipBatchPlan(['a.mp4', 'b.mp4'].map(file), shots);
assert.equal(none.matched.length, 0, 'no matches');
assert.equal(none.skipped.length, 2, 'both reported as skipped');

// --- every reason has a Vietnamese label ----------------------------------------
for (const reason of ['not_a_number', 'no_such_segment', 'duplicate_segment']) {
  const label = clipBatchSkipReasonLabel(reason);
  assert.ok(label && label.length > 0, `label for ${reason}`);
  assert.ok(!/undefined/.test(label), `label for ${reason} is real text`);
}

// --- the batch upload fan-out ----------------------------------------------------
const { runClipBatchUpload } = await import(
  pathToFileURL(join(root, 'src/lib/clipBatchUpload.ts')).href
);

const entriesFor = (orders) => orders.map((order) => ({ shotOrder: order, name: `${order}.mp4` }));

// One file failing must not cost the others, and nothing is undone.
const midFailure = await runClipBatchUpload(entriesFor([1, 2, 3, 4]), async (entry) => {
  if (entry.shotOrder === 3) throw new Error('File clip quá lớn.');
  return { id: `clip-${entry.shotOrder}` };
});
assert.deepEqual(
  midFailure.succeeded.map((entry) => entry.shotOrder),
  [1, 2, 4],
  'every other file still loads when one fails',
);
assert.equal(midFailure.failed.length, 1, 'exactly one failure');
assert.equal(midFailure.failed[0].shotOrder, 3, 'the failure names its segment');
assert.equal(midFailure.failed[0].name, '3.mp4', 'the failure names its file');
assert.equal(midFailure.failed[0].message, 'File clip quá lớn.', 'the backend message is kept');
assert.equal(midFailure.total, 4, 'total counts every matched file');
assert.equal(midFailure.succeeded[0].clip.id, 'clip-1', 'the created clip is returned');

// Every file failing still reports per file rather than throwing.
const allFailed = await runClipBatchUpload(entriesFor([1, 2]), async () => {
  throw new Error('Định dạng clip chưa được hỗ trợ.');
});
assert.equal(allFailed.succeeded.length, 0, 'nothing loaded');
assert.equal(allFailed.failed.length, 2, 'both reported');
assert.deepEqual(allFailed.failed.map((entry) => entry.shotOrder), [1, 2], 'in input order');

// A non-Error rejection still yields a readable message.
const thrownString = await runClipBatchUpload(entriesFor([1]), async () => {
  throw 'mất kết nối';
});
assert.equal(thrownString.failed[0].message, 'mất kết nối', 'non-Error rejection is stringified');

// Results follow the caller's order even when requests finish out of order.
const settleOrder = [];
const outOfOrder = await runClipBatchUpload(
  entriesFor([1, 2, 3, 4, 5, 6]),
  async (entry) => {
    // Later segments resolve first.
    await new Promise((resolve) => setTimeout(resolve, (7 - entry.shotOrder) * 5));
    settleOrder.push(entry.shotOrder);
    return { id: `clip-${entry.shotOrder}` };
  },
  { concurrency: 6 },
);
assert.deepEqual(
  outOfOrder.succeeded.map((entry) => entry.shotOrder),
  [1, 2, 3, 4, 5, 6],
  'report is in segment order, not completion order',
);
assert.notDeepEqual(settleOrder, [1, 2, 3, 4, 5, 6], 'requests really did finish out of order');

// Concurrency is respected and every file is uploaded exactly once.
let inFlight = 0;
let peakInFlight = 0;
const uploadedNames = [];
const progress = [];
const limited = await runClipBatchUpload(
  entriesFor(Array.from({ length: 18 }, (_, index) => index + 1)),
  async (entry) => {
    inFlight += 1;
    peakInFlight = Math.max(peakInFlight, inFlight);
    await new Promise((resolve) => setTimeout(resolve, 1));
    uploadedNames.push(entry.name);
    inFlight -= 1;
    return { id: `clip-${entry.shotOrder}` };
  },
  { concurrency: 4, onProgress: (done, total) => progress.push([done, total]) },
);
assert.equal(limited.succeeded.length, 18, 'all 18 load');
assert.equal(peakInFlight, 4, 'never more than the configured lanes in flight');
assert.equal(new Set(uploadedNames).size, 18, 'each file uploaded exactly once');
assert.equal(progress.length, 18, 'progress reported per file');
assert.deepEqual(progress.at(-1), [18, 18], 'progress ends at the total');

// An empty batch does not hang on a zero-lane worker pool.
const empty = await runClipBatchUpload([], async () => {
  throw new Error('should never be called');
});
assert.deepEqual(empty, { succeeded: [], failed: [], total: 0 }, 'empty batch is a no-op');

console.log('AI Video clip batch matching verification passed.');
