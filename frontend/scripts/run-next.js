'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { randomUUID } = require('crypto');

const NEXT_BINARY = require.resolve('next/dist/bin/next');
const { processEnv, updateInitialEnv } = require(require.resolve('@next/env', {
  paths: [path.dirname(NEXT_BINARY)],
}));

const APPLICATION_KEYS = new Set([
  'GOOGLE_CLIENT_ID', 'NEXT_PUBLIC_GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET',
  'NEXTAUTH_SECRET', 'NEXTAUTH_URL', 'NEXTAUTH_URL_INTERNAL', 'ADMIN_EMAILS',
  'ADMIN_API_TOKEN', 'INTERNAL_IDENTITY_SECRET', 'API_URL', 'NEXT_PUBLIC_API_URL',
]);
const RUNTIME_KEYS = new Set([
  'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'USER', 'LOGNAME', 'SHELL', 'LANG',
  'LC_ALL', 'TZ', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'PORT', 'NODE_ENV',
  'NEXT_TELEMETRY_DISABLED', 'NEXT_TRACE_UPLOAD_DISABLED', 'CI',
]);
const PUBLIC_APPLICATION_KEYS = new Set(['NEXT_PUBLIC_GOOGLE_CLIENT_ID', 'NEXT_PUBLIC_API_URL']);
const FRONTEND_DIRECTORY = path.resolve(__dirname, '..');
const ROOT_DIRECTORY = path.resolve(FRONTEND_DIRECTORY, '..');
const VALUE_OPTIONS = new Set([
  '--port', '-p', '--hostname', '-H', '--keepAliveTimeout', '--experimental-https-key',
  '--experimental-https-cert', '--experimental-https-ca', '--experimental-upload-trace',
  '--debug-build-paths',
]);
const OPTIONAL_VALUE_OPTIONS = new Set(['--inspect', '--experimental-build-mode', '--internal-trace']);

function failConfiguration() {
  throw new Error('Next configuration error.');
}

function regularFileContents(filePath, legacyPath) {
  let entry;
  try {
    entry = fs.lstatSync(filePath);
  } catch (error) {
    if (error && error.code === 'ENOENT') return null;
    failConfiguration();
  }

  if (entry.isSymbolicLink()) {
    if (legacyPath && fs.readlinkSync(filePath) === '../.env') return { legacy: true };
    failConfiguration();
  }
  if (!entry.isFile()) failConfiguration();

  let descriptor;
  try {
    descriptor = fs.openSync(filePath, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    if (!fs.fstatSync(descriptor).isFile()) failConfiguration();
    return { path: filePath, contents: fs.readFileSync(descriptor, 'utf8'), env: {} };
  } catch {
    failConfiguration();
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
  return null;
}

function environmentEntries(mode) {
  const names = [`.env.${mode}.local`, '.env.local', `.env.${mode}`, '.env'];
  const entries = [];
  let legacyLink = null;
  for (const name of names) {
    const filePath = path.join(FRONTEND_DIRECTORY, name);
    const entry = regularFileContents(filePath, name === '.env');
    if (!entry) continue;
    if (entry.legacy) {
      legacyLink = filePath;
      continue;
    }
    entries.push({ entry, frontend: true });
  }
  for (const name of names) {
    const entry = regularFileContents(path.join(ROOT_DIRECTORY, name), false);
    if (entry) entries.push({ entry, frontend: false });
  }
  return { entries, legacyLink };
}

function validNextOptions(options) {
  for (let index = 0; index < options.length; index += 1) {
    const option = options[index];
    if (option === '--' || !option.startsWith('-')) return false;
    const name = option.split('=', 1)[0];
    if (VALUE_OPTIONS.has(name) && !option.includes('=')) {
      const value = options[index + 1];
      if (value === undefined || value === '--') return false;
      index += 1;
    } else if (OPTIONAL_VALUE_OPTIONS.has(name) && !option.includes('=') && options[index + 1] !== undefined && !options[index + 1].startsWith('-')) {
      index += 1;
    }
  }
  return true;
}

function secureNextDirectory() {
  const nextDirectory = path.join(FRONTEND_DIRECTORY, '.next');
  let nextEntry;
  try {
    nextEntry = fs.lstatSync(nextDirectory);
  } catch (error) {
    if (!error || error.code !== 'ENOENT') failConfiguration();
    fs.mkdirSync(nextDirectory, { mode: 0o700 });
    nextEntry = fs.lstatSync(nextDirectory);
  }
  if (nextEntry.isSymbolicLink() || !nextEntry.isDirectory()) failConfiguration();

  let descriptor;
  try {
    descriptor = fs.openSync(nextDirectory, fs.constants.O_RDONLY | fs.constants.O_DIRECTORY | fs.constants.O_NOFOLLOW);
    const opened = fs.fstatSync(descriptor);
    if (!opened.isDirectory()) failConfiguration();
    fs.fchmodSync(descriptor, 0o700);
    const secured = fs.fstatSync(descriptor);
    const current = fs.lstatSync(nextDirectory);
    if (!secured.isDirectory() || (secured.mode & 0o777) !== 0o700 || current.isSymbolicLink() || !current.isDirectory() || current.dev !== secured.dev || current.ino !== secured.ino) {
      failConfiguration();
    }
  } catch {
    failConfiguration();
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function clearProcessEnvironment() {
  for (const key of Object.keys(process.env)) delete process.env[key];
}

function rawMarker(entries, parent) {
  const values = [...entries.map(({ entry }) => entry.contents), ...Object.values(parent)];
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const marker = `\uE000${randomUUID()}\uE001`;
    if (!values.some((value) => String(value).includes(marker))) return marker;
  }
  failConfiguration();
}

function restoreRawEntries(entries, parent) {
  const marker = rawMarker(entries, parent);
  const rawEntries = entries.map(({ entry }) => ({
    ...entry,
    contents: entry.contents.replaceAll('$', marker),
    env: {},
  }));
  clearProcessEnvironment();
  try {
    processEnv(rawEntries, FRONTEND_DIRECTORY, { error: failConfiguration }, true);
  } catch {
    failConfiguration();
  }
  for (let index = 0; index < entries.length; index += 1) {
    entries[index].entry.env = Object.fromEntries(Object.entries(rawEntries[index].env).map(([key, value]) => [key, value.replaceAll(marker, '$')]));
  }
}

function effectiveRawApplicationValues(entries, parentApplication) {
  const effective = { ...parentApplication };
  for (const { entry } of entries) {
    for (const [key, value] of Object.entries(entry.env)) {
      if (APPLICATION_KEYS.has(key) && effective[key] === undefined) effective[key] = value;
    }
  }
  return effective;
}

function referencesIn(value) {
  const references = new Set();
  for (let index = value.indexOf('$'); index !== -1; index = value.indexOf('$', index + 1)) {
    // Literal $(...) is not expanded by dotenv. Other bare/escaped dollars can
    // construct a new variable name during recursion or Next's second load.
    if (value[index + 1] === '(') continue;
    if (value[index - 1] === '\\') failConfiguration();
    const match = /^\$\{?([A-Za-z0-9_]+)/.exec(value.slice(index));
    if (!match) failConfiguration();
    references.add(match[1]);
  }
  return references;
}

function validateRawReferences(effective) {
  for (const [key, value] of Object.entries(effective)) {
    if (!APPLICATION_KEYS.has(key)) continue;
    const allowed = PUBLIC_APPLICATION_KEYS.has(key) ? PUBLIC_APPLICATION_KEYS : APPLICATION_KEYS;
    if ([...referencesIn(value)].some((reference) => !allowed.has(reference))) failConfiguration();
  }
}

function childEnvironment(command) {
  if (!(fs.constants.O_NOFOLLOW > 0 && fs.constants.O_DIRECTORY > 0)) failConfiguration();
  const mode = command === 'dev' ? 'development' : 'production';
  const parent = { ...process.env };
  const parentApplication = {};
  const parentRuntime = {};
  for (const key of APPLICATION_KEYS) {
    if (parent[key] !== undefined) parentApplication[key] = parent[key];
  }
  for (const key of RUNTIME_KEYS) {
    if (parent[key] !== undefined) parentRuntime[key] = parent[key];
  }
  const parserEnvironment = { ...parentApplication, ...parentRuntime };
  parserEnvironment.NODE_ENV = mode;

  const { entries, legacyLink } = environmentEntries(mode);
  restoreRawEntries(entries, parent);
  for (const { entry, frontend } of entries) {
    if (frontend && Object.keys(entry.env).some((key) => !APPLICATION_KEYS.has(key))) {
      failConfiguration();
    }
  }
  validateRawReferences(effectiveRawApplicationValues(entries, parentApplication));

  clearProcessEnvironment();
  Object.assign(process.env, parserEnvironment);
  updateInitialEnv(parserEnvironment);
  let combined;
  try {
    [combined] = processEnv(entries.map(({ entry }) => entry), FRONTEND_DIRECTORY, {
      error: failConfiguration,
    }, true);
  } catch {
    failConfiguration();
  }

  validateRawReferences(combined);
  secureNextDirectory();
  if (legacyLink) {
    const legacyEntry = fs.lstatSync(legacyLink);
    if (!legacyEntry.isSymbolicLink() || fs.readlinkSync(legacyLink) !== '../.env') failConfiguration();
    fs.unlinkSync(legacyLink);
  }

  // Runtime controls come only from the caller, never from root dotenv values.
  const child = { ...parentRuntime };
  for (const key of APPLICATION_KEYS) {
    if (combined[key] !== undefined) child[key] = combined[key];
  }
  child.NODE_ENV = mode;
  return child;
}

function run() {
  const [command, ...options] = process.argv.slice(2);
  if (!['dev', 'build', 'start'].includes(command)) {
    process.stderr.write('Usage: run-next.js <dev|build|start> [...Next args]\n');
    process.exitCode = 1;
    return;
  }
  if (!validNextOptions(options)) {
    process.stderr.write('Invalid Next arguments.\n');
    process.exitCode = 1;
    return;
  }

  let environment;
  try {
    environment = childEnvironment(command);
  } catch {
    process.stderr.write('Next configuration error.\n');
    process.exitCode = 1;
    return;
  }

  const child = spawn(process.execPath, [NEXT_BINARY, command, FRONTEND_DIRECTORY, ...options], {
    cwd: FRONTEND_DIRECTORY,
    env: environment,
    stdio: 'inherit',
  });
  let forwardedSignal = null;
  const forward = (signal) => {
    forwardedSignal ||= signal;
    child.kill(signal);
  };
  const forwardInterrupt = () => forward('SIGINT');
  const forwardTermination = () => forward('SIGTERM');
  process.on('SIGINT', forwardInterrupt);
  process.on('SIGTERM', forwardTermination);
  child.on('error', () => process.exit(1));
  child.on('exit', (code, signal) => {
    process.off('SIGINT', forwardInterrupt);
    process.off('SIGTERM', forwardTermination);
    if (signal || forwardedSignal) process.kill(process.pid, signal || forwardedSignal);
    else process.exit(code === null ? 1 : code);
  });
}

run();
