#!/usr/bin/env node

const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');

const projectRoot = path.resolve(__dirname, '..');
const isWindows = process.platform === 'win32';
const args = new Set(process.argv.slice(2));
const backendOnly = args.has('--backend-only');
const frontendOnly = args.has('--frontend-only');

if (backendOnly && frontendOnly) {
  console.error('Use either --backend-only or --frontend-only, not both.');
  process.exit(1);
}

const backendHost = process.env.VOICEBOX_BACKEND_HOST || '127.0.0.1';
const backendPort = process.env.VOICEBOX_BACKEND_PORT || process.env.VOICEBOX_PORT || '17493';
const frontendPort = process.env.VOICEBOX_FRONTEND_PORT || '5173';
const browserBackendHost = backendHost === '0.0.0.0' ? '127.0.0.1' : backendHost;
const backendUrl = `http://${browserBackendHost}:${backendPort}`;
const backendReadyUrl = `${backendUrl}/health/ready`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const startedChildren = [];
let shuttingDown = false;

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function buildEnv() {
  const cacheRoot = path.join(projectRoot, '.cache');
  const dataRoot = path.join(projectRoot, 'data');
  const modelsRoot = path.join(dataRoot, 'models');
  const tempRoot = path.join(cacheRoot, 'temp');
  const dirs = [
    tempRoot,
    path.join(cacheRoot, 'pip'),
    path.join(cacheRoot, 'bun'),
    path.join(cacheRoot, 'torch'),
    path.join(cacheRoot, 'uv'),
    path.join(cacheRoot, 'numba'),
    modelsRoot,
    path.join(modelsRoot, '.hf'),
    path.join(modelsRoot, '.xet'),
    path.join(dataRoot, 'cache'),
    path.join(projectRoot, '.logs'),
  ];

  for (const dir of dirs) {
    ensureDir(dir);
  }

  const env = {
    ...process.env,
    TMP: tempRoot,
    TEMP: tempRoot,
    TMPDIR: tempRoot,
    PIP_CACHE_DIR: path.join(cacheRoot, 'pip'),
    BUN_INSTALL_CACHE_DIR: path.join(cacheRoot, 'bun'),
    UV_CACHE_DIR: path.join(cacheRoot, 'uv'),
    HF_HOME: path.join(modelsRoot, '.hf'),
    HF_HUB_CACHE: modelsRoot,
    HF_XET_CACHE: path.join(modelsRoot, '.xet'),
    TRANSFORMERS_CACHE: modelsRoot,
    TORCH_HOME: path.join(cacheRoot, 'torch'),
    XDG_CACHE_HOME: cacheRoot,
    NUMBA_CACHE_DIR: path.join(cacheRoot, 'numba'),
    CUDA_MODULE_LOADING: 'LAZY',
    PYTORCH_CUDA_ALLOC_CONF: 'expandable_segments:True',
    VOICEBOX_DATA_DIR: process.env.VOICEBOX_DATA_DIR || dataRoot,
    VOICEBOX_MODELS_DIR: process.env.VOICEBOX_MODELS_DIR || modelsRoot,
    VOICEBOX_CACHE_DIR: process.env.VOICEBOX_CACHE_DIR || path.join(dataRoot, 'cache'),
    VOICEBOX_BACKEND_HOST: backendHost,
    VOICEBOX_BACKEND_PORT: backendPort,
    VOICEBOX_FRONTEND_PORT: frontendPort,
    VITE_SERVER_URL: process.env.VITE_SERVER_URL || backendUrl,
  };

  const soxDir = path.join(projectRoot, 'tools', 'sox-14.4.2');
  if (fs.existsSync(soxDir)) {
    env.Path = [soxDir, env.Path || env.PATH].filter(Boolean).join(path.delimiter);
    env.PATH = env.Path;
  }

  return env;
}

const runtimeEnv = buildEnv();

function commandPath(name) {
  const lookup = isWindows ? 'where.exe' : 'which';
  const result = spawnSync(lookup, [name], {
    cwd: projectRoot,
    encoding: 'utf8',
    env: runtimeEnv,
  });

  if (result.status !== 0 || !result.stdout.trim()) {
    return null;
  }

  const candidates = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!isWindows) {
    return candidates[0];
  }

  return candidates.find((candidate) => /\.(exe|cmd|bat)$/i.test(candidate)) || candidates[0];
}

function quoteCmdArg(value) {
  const text = String(value);
  if (!text) {
    return '""';
  }
  if (!/[^-\w@%+=:,./\\]/.test(text)) {
    return text;
  }
  return `"${text.replace(/"/g, '\\"')}"`;
}

function spawnInvocation(command, args) {
  if (!isWindows) {
    return { command, args };
  }

  if (/\.(cmd|bat)$/i.test(command)) {
    const commandLine = [command, ...args].map(quoteCmdArg).join(' ');
    return {
      command: process.env.ComSpec || 'cmd.exe',
      args: ['/d', '/s', '/c', commandLine],
    };
  }

  if (/\.ps1$/i.test(command)) {
    return {
      command: 'powershell.exe',
      args: ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', command, ...args],
    };
  }

  return { command, args };
}

function findPython() {
  const venvPython = isWindows
    ? path.join(projectRoot, 'backend', 'venv', 'Scripts', 'python.exe')
    : path.join(projectRoot, 'backend', 'venv', 'bin', 'python');

  if (fs.existsSync(venvPython)) {
    return venvPython;
  }

  for (const name of isWindows ? ['python'] : ['python3', 'python']) {
    const found = commandPath(name);
    if (found) {
      return found;
    }
  }

  return null;
}

function canImport(python, moduleName) {
  const result = spawnSync(python, ['-c', `import ${moduleName}`], {
    cwd: projectRoot,
    env: runtimeEnv,
    stdio: 'ignore',
  });
  return result.status === 0;
}

function packageManagerPreference() {
  const userAgent = process.env.npm_config_user_agent || '';

  if (userAgent.includes('npm/')) {
    return ['npm', 'bun', 'pnpm', 'yarn'];
  }
  if (userAgent.includes('bun/')) {
    return ['bun', 'npm', 'pnpm', 'yarn'];
  }
  if (userAgent.includes('pnpm/')) {
    return ['pnpm', 'bun', 'npm', 'yarn'];
  }
  if (userAgent.includes('yarn/')) {
    return ['yarn', 'bun', 'npm', 'pnpm'];
  }
  if (fs.existsSync(path.join(projectRoot, 'bun.lock'))) {
    return ['bun', 'npm', 'pnpm', 'yarn'];
  }
  return ['npm', 'bun', 'pnpm', 'yarn'];
}

function findPackageManager() {
  for (const name of packageManagerPreference()) {
    const found = commandPath(name);
    if (found) {
      if (isWindows && name === 'npm') {
        const npmCli = path.join(path.dirname(found), 'node_modules', 'npm', 'bin', 'npm-cli.js');
        if (fs.existsSync(npmCli)) {
          return { name, command: process.execPath, baseArgs: [npmCli] };
        }
      }

      return { name, command: found, baseArgs: [] };
    }
  }

  return null;
}

function runArgs(packageManager, scriptName, scriptArgs = []) {
  if (packageManager === 'npm' || packageManager === 'pnpm') {
    return ['run', scriptName, '--', ...scriptArgs];
  }
  if (packageManager === 'yarn') {
    return [scriptName, ...scriptArgs];
  }
  return ['run', scriptName, ...scriptArgs];
}

function installArgs(packageManager) {
  if (packageManager === 'yarn') {
    return ['install'];
  }
  return ['install'];
}

function runForeground(command, args, cwd) {
  const invocation = spawnInvocation(command, args);
  const result = spawnSync(invocation.command, invocation.args, {
    cwd,
    env: runtimeEnv,
    stdio: 'inherit',
  });

  if (result.status !== 0) {
    throw new Error(`${path.basename(command)} ${args.join(' ')} failed`);
  }
}

function needInstall() {
  return (
    !fs.existsSync(path.join(projectRoot, 'node_modules')) &&
    !fs.existsSync(path.join(projectRoot, 'web', 'node_modules'))
  );
}

function isUrlReady(url) {
  return new Promise((resolve) => {
    const client = url.startsWith('https:') ? https : http;
    const request = client.get(url, { timeout: 2000 }, (response) => {
      response.resume();
      resolve(response.statusCode >= 200 && response.statusCode < 500);
    });

    request.on('timeout', () => {
      request.destroy();
      resolve(false);
    });
    request.on('error', () => resolve(false));
  });
}

function pipeWithPrefix(stream, label, isError = false) {
  let buffer = '';
  const output = isError ? process.stderr : process.stdout;

  stream.on('data', (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || '';

    for (const line of lines) {
      output.write(line ? `[${label}] ${line}\n` : '\n');
    }
  });

  stream.on('end', () => {
    if (buffer) {
      output.write(`[${label}] ${buffer}\n`);
    }
  });
}

function startProcess(label, command, args, cwd) {
  const invocation = spawnInvocation(command, args);
  const child = spawn(invocation.command, invocation.args, {
    cwd,
    env: runtimeEnv,
    detached: !isWindows,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  pipeWithPrefix(child.stdout, label);
  pipeWithPrefix(child.stderr, label, true);

  child.on('exit', (code, signal) => {
    if (shuttingDown) {
      return;
    }

    const reason = signal ? `signal ${signal}` : `exit code ${code}`;
    console.error(`${label} stopped unexpectedly (${reason}).`);
    shutdown(code || 1);
  });

  startedChildren.push({ child, label });
  return child;
}

async function waitForUrl(name, url, timeoutMs, child) {
  process.stdout.write(`Waiting for ${name}: ${url}`);
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    if (await isUrlReady(url)) {
      process.stdout.write(`\n${name} ready: ${url}\n`);
      return;
    }

    if (child && child.exitCode !== null) {
      throw new Error(`${name} exited before it became ready.`);
    }

    process.stdout.write('.');
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  process.stdout.write('\n');
  throw new Error(`${name} did not become ready after ${timeoutMs / 1000}s.`);
}

function terminateChild(child) {
  if (!child || child.exitCode !== null) {
    return;
  }

  if (isWindows) {
    spawnSync('taskkill.exe', ['/pid', String(child.pid), '/t', '/f'], {
      stdio: 'ignore',
    });
    return;
  }

  try {
    process.kill(-child.pid, 'SIGTERM');
  } catch {
    child.kill('SIGTERM');
  }
}

function shutdown(exitCode = 0) {
  if (shuttingDown) {
    return;
  }

  shuttingDown = true;
  for (const { child } of startedChildren) {
    terminateChild(child);
  }
  process.exit(exitCode);
}

process.on('SIGINT', () => shutdown(0));
process.on('SIGTERM', () => shutdown(0));

async function main() {
  console.log('Starting Voicebox development environment');
  console.log(`Project:  ${projectRoot}`);
  console.log(`Backend:  ${backendUrl}`);
  console.log(`Frontend: ${frontendUrl}`);

  let backendChild = null;
  let frontendChild = null;

  if (!frontendOnly) {
    if (await isUrlReady(backendReadyUrl)) {
      console.log(`Backend already running: ${backendUrl}`);
    } else {
      const python = findPython();
      if (!python) {
        throw new Error('Python was not found. Create backend/venv or install Python.');
      }
      const missing = ['uvicorn', 'fastapi'].filter((moduleName) => !canImport(python, moduleName));
      if (missing.length) {
        throw new Error(
          `Missing Python packages: ${missing.join(
            ', ',
          )}. Run: ${python} -m pip install -r backend/requirements.txt`,
        );
      }

      backendChild = startProcess(
        'backend',
        python,
        ['-m', 'backend.main', '--host', backendHost, '--port', backendPort],
        projectRoot,
      );
      await waitForUrl('Backend', backendReadyUrl, 180000, backendChild);
    }
  }

  if (!backendOnly) {
    if (await isUrlReady(frontendUrl)) {
      console.log(`Frontend already running: ${frontendUrl}`);
    } else {
      const packageManager = findPackageManager();
      if (!packageManager) {
        throw new Error('No package manager found. Install npm, bun, pnpm, or yarn.');
      }

      if (needInstall()) {
        console.log(`Installing JavaScript dependencies with ${packageManager.name}...`);
        runForeground(
          packageManager.command,
          [...packageManager.baseArgs, ...installArgs(packageManager.name)],
          projectRoot,
        );
      }

      frontendChild = startProcess(
        'frontend',
        packageManager.command,
        [
          ...packageManager.baseArgs,
          ...runArgs(packageManager.name, 'dev', [
            '--host',
            '127.0.0.1',
            '--port',
            frontendPort,
            '--strictPort',
          ]),
        ],
        path.join(projectRoot, 'web'),
      );
      await waitForUrl('Frontend', frontendUrl, 90000, frontendChild);
    }
  }

  console.log('');
  console.log('Voicebox development environment is ready.');
  if (!frontendOnly) {
    console.log(`Backend API/docs: ${backendUrl}/docs`);
  }
  if (!backendOnly) {
    console.log(`Frontend:         ${frontendUrl}`);
  }
  console.log('Press Ctrl+C to stop services started by this command.');
}

main().catch((error) => {
  console.error('');
  console.error(error.message || error);
  shutdown(1);
});
