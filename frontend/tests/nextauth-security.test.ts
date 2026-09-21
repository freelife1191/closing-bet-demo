import { execFileSync } from 'node:child_process';
import { expect, it } from 'vitest';

// A real Node process avoids jsdom's distinct Headers/Uint8Array realms.
it('preserves real NextAuth session decoding and rejects malformed bearer headers', () => {
  const script = `
    const { NextRequest } = require('next/server');
    const { encode, getToken } = require('next-auth/jwt');
    (async () => {
      const secret = 'dependency-upgrade-synthetic-secret';
      const results = [];
      for (const authorization of ['Bearer %', 'Bearer %E0%A4%A', 'Bearer invalid-token']) {
        const req = new NextRequest('http://qa.invalid/api/kr/user/quota', { headers: { authorization } });
        try { results.push(await getToken({ req, secret })); }
        catch (error) { results.push({ error: error.name }); }
      }
      results.push(await getToken({ req: new NextRequest('http://qa.invalid/api/kr/user/quota'), secret }));
      const token = await encode({ token: { email: 'qa@example.invalid' }, secret });
      const req = new NextRequest('http://qa.invalid/api/kr/user/quota', {
        headers: { cookie: 'next-auth.session-token=' + token },
      });
      const session = await getToken({ req, secret, secureCookie: false });
      results.push(session?.email);
      console.log(JSON.stringify(results));
    })().catch(error => { console.error(error); process.exitCode = 1; });
  `;
  const output = execFileSync(process.execPath, ['-e', script], {
    cwd: process.cwd(),
    env: { PATH: process.env.PATH, NODE_ENV: 'test' },
    encoding: 'utf8',
    timeout: 15_000,
  });
  expect(JSON.parse(output)).toEqual([null, null, null, null, 'qa@example.invalid']);
});
