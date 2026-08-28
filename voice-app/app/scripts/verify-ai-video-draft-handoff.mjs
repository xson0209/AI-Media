import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  aiVideoDraftFormConfig,
  videoInspirationDraftConfig,
} from '../src/lib/aiVideoDraft.ts';

const vietnameseConfig = videoInspirationDraftConfig('vi');
assert.deepEqual(vietnameseConfig, {
  targetLanguage: 'vi',
  videoPurpose: 'custom',
  dialogueMode: 'voiceover',
  narrationDensity: 'balanced',
  callToActionStyle: 'none',
});

assert.deepEqual(
  aiVideoDraftFormConfig({
    source: 'video-inspiration',
    createdAt: '2026-08-11T00:00:00.000Z',
    sources: [],
    ...vietnameseConfig,
  }),
  vietnameseConfig,
);

assert.deepEqual(
  aiVideoDraftFormConfig({
    source: 'video-inspiration',
    createdAt: '2026-08-11T00:00:00.000Z',
    sources: [],
  }),
  {},
  'Legacy drafts without output config must keep the current form values.',
);

const [videoInspirationSource, aiVideoAssistantSource] = await Promise.all([
  readFile(new URL('../src/components/VideoInspiration/VideoInspiration.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../src/components/AIVideoAssistant/AIVideoAssistant.tsx', import.meta.url),
    'utf8',
  ),
]);

assert.match(
  videoInspirationSource,
  /\.\.\.videoInspirationDraftConfig\(job\.target_language\)/,
  'Video Inspiration must write the source job language and coherent output defaults into the draft.',
);
assert.match(
  videoInspirationSource,
  /\['Video Inspiration job ID', job\.id\]/,
  'The draft must retain the source Video Inspiration job ID.',
);
assert.match(
  videoInspirationSource,
  /\['Tên file nguồn', job\.original_filename\]/,
  'The draft must retain the uploaded source filename when available.',
);
assert.match(
  videoInspirationSource,
  /\['Link nguồn', job\.source_url\]/,
  'The draft must retain the source URL when available.',
);
assert.match(
  aiVideoAssistantSource,
  /\.\.\.aiVideoDraftFormConfig\(draft\)/,
  'AI Video must hydrate output config from the handoff draft before creating the project.',
);

console.log('AI Video draft handoff verifier passed.');
