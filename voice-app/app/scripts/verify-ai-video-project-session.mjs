// Builds the real hook with a real router, then exercises browser navigation and storage.
// Uses Playwright from the existing backend Python environment; no AI/backend requests.
import { existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';

const appRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const workspace = dirname(appRoot);
const result = await build({
  configFile: false,
  root: appRoot,
  logLevel: 'error',
  define: { 'process.env.NODE_ENV': JSON.stringify('development') },
  build: {
    write: false,
    outDir: join(tmpdir(), `ai-video-session-build-${process.pid}`),
    minify: false,
    lib: { entry: join(appRoot, 'scripts/fixtures/ai-video-project-session.tsx'), formats: ['es'] },
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
const bundle = (Array.isArray(result) ? result[0] : result).output.find(
  (output) => output.type === 'chunk' && output.isEntry,
);
if (!bundle) throw new Error('Project-session fixture did not produce a browser entry.');

const server = createServer((request, response) => {
  if (request.url === '/fixture.js') {
    response.writeHead(200, { 'Content-Type': 'text/javascript; charset=utf-8' });
    response.end(bundle.code);
    return;
  }
  response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  response.end(
    '<!doctype html><html lang="vi"><meta charset="utf-8"><div id="root"></div><script type="module" src="/fixture.js"></script></html>',
  );
});
await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', resolve);
});

try {
  const localPython = join(
    workspace,
    'backend/venv',
    process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
  );
  const python = process.env.PYTHON || (existsSync(localPython) ? localPython : 'python');
  const address = server.address();
  const child = spawn(
    python,
    [
      join(appRoot, 'scripts/verify-ai-video-project-session.py'),
      `http://127.0.0.1:${address.port}`,
    ],
    { stdio: 'inherit', env: { ...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1' } },
  );
  const exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', resolve);
  });
  if (exitCode !== 0) process.exitCode = exitCode || 1;
} finally {
  await new Promise((resolve) => server.close(resolve));
}
