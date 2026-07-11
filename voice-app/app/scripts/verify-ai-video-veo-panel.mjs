import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const panel = readFileSync(join(root, 'src/components/AIVideoAssistant/AIVideoVeoChromePanel.tsx'), 'utf8');
const types = readFileSync(join(root, 'src/lib/api/types.ts'), 'utf8');
const client = readFileSync(join(root, 'src/lib/api/client.ts'), 'utf8');

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`Missing ${label}: ${needle}`);
  }
}

function assertAll(source, needles, label) {
  for (const needle of needles) {
    assertContains(source, needle, label);
  }
}

assertAll(panel, ['Chưa cấu hình phiên Veo3/Chrome', 'needs_login', 'checking', 'ready', 'invalid', 'mismatch'], 'session state');
assertAll(panel, ['Đăng nhập Google kết nối Veo3', 'Đang dùng:', 'Kiểm tra phiên', 'Đổi tài khoản'], 'session action');
assertAll(panel, ['Nhãn kết nối', 'Sửa nhãn', 'Xác nhận dùng tài khoản này'], 'identity label action');
assertAll(panel, ['getDefaultVeoProviderSession', "queryKey: ['ai-video', 'veo-session-default']"], 'default session reuse');
assertAll(panel, ['Chờ tạo clip', 'submitting_prompt', 'waiting_generation', 'downloading', 'importing', 'completed', 'failed', 'needs_login'], 'job item progress');
assertAll(panel, ['Retry lỗi', 'Resume', 'Hủy job'], 'retry resume cancel action');
assertAll(panel, ['Phê duyệt, không hỏi lại', 'Phê duyệt thủ công từng lần', 'Phê duyệt lần này'], 'credit policy');
assertAll(panel, ['render_job_id', "queryKey: ['ai-video', 'render']", "queryKey: ['ai-video', 'render-job-latest', projectId]"], 'auto-render invalidation');
assertAll(types, ['not_configured', 'pending', 'VideoProviderSessionResponse', 'VideoClipGenerationJobResponse', 'VideoClipGenerationItemStatus'], 'frontend types');
assertAll(client, ['startVideoClipGenerationJob', 'retryVideoClipGenerationJob', 'resumeVideoClipGenerationJob', 'approveVideoClipGenerationCredit'], 'api client methods');

console.log('AI Video Veo panel verification passed.');
