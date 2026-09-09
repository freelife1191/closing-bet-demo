// Explicit build checks: run separately from Vitest to avoid shared .next writes.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { before, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const cwd = fileURLToPath(new URL('../../', import.meta.url));
let output;
before(() => {
  output = execFileSync('npm', ['run', 'build'], {
    cwd, encoding: 'utf8', timeout: 180_000, stdio: ['ignore', 'pipe', 'inherit'],
  });
  process.stdout.write(output);
});

test('application builds successfully', () => {
  assert.match(output, /Compiled successfully/);
  assert.match(output, /Creating an optimized production build/);
});

test('build contains required routes', () => {
  for (const route of ['/', '/dashboard/kr', '/dashboard/kr/closing-bet', '/dashboard/kr/vcp', '/dashboard/kr/cumulative']) {
    assert.ok(output.split('\n').some((line) => line.trim().split(/\s+/).at(-1) === route), `Missing route: ${route}`);
  }
});

test('TypeScript compiles without errors', () => {
  execFileSync('npm', ['run', 'type-check'], {
    cwd, timeout: 60_000, stdio: 'inherit',
  });
});
