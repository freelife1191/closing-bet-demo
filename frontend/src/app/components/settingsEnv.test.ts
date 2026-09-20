import { describe, it, expect } from 'vitest';
import { pickNotificationEnv, storedEnvFieldProps } from './settingsEnv';

describe('storedEnvFieldProps', () => {
  it('turns a masked server value into a placeholder, never a value', () => {
    expect(storedEnvFieldProps('sk-1***************abcd', 'sk-...')).toEqual({
      value: '',
      placeholder: '저장되어 있습니다. 바꾸려면 새 값을 입력하세요',
    });
  });

  it('never puts the masked string on screen — a password placeholder is plain text', () => {
    const { placeholder } = storedEnvFieldProps('sk-1***************abcd', 'sk-...');
    expect(placeholder).not.toContain('sk-1');
    expect(placeholder).not.toContain('abcd');
  });

  it('treats a fully masked short value as masked too', () => {
    // _mask_env_value returns all asterisks when the secret is 8 chars or fewer
    expect(storedEnvFieldProps('******', 'sk-...').value).toBe('');
  });

  it('edits what the user typed rather than replacing it with a hint', () => {
    expect(storedEnvFieldProps('sk-typed-by-user', 'sk-...')).toEqual({
      value: 'sk-typed-by-user',
      placeholder: 'sk-...',
    });
  });

  it('falls back to the hint when no key is stored', () => {
    expect(storedEnvFieldProps(undefined, 'pplx-...')).toEqual({
      value: '',
      placeholder: 'pplx-...',
    });
  });

  it('treats a cleared field as empty, not as a stored key', () => {
    expect(storedEnvFieldProps('', 'pplx-...')).toEqual({
      value: '',
      placeholder: 'pplx-...',
    });
  });
});

describe('pickNotificationEnv', () => {
  it('leaves API keys out — a test send must not write them', () => {
    const picked = pickNotificationEnv({
      OPENAI_API_KEY: '',
      PERPLEXITY_API_KEY: 'pplx-abc',
      DISCORD_WEBHOOK_URL: 'https://discord/webhook',
    });
    expect(picked).toEqual({ DISCORD_WEBHOOK_URL: 'https://discord/webhook' });
  });

  it('carries every notification field the server needs to send', () => {
    const all = {
      TELEGRAM_BOT_TOKEN: 't',
      TELEGRAM_CHAT_ID: 'c',
      DISCORD_WEBHOOK_URL: 'd',
      SMTP_HOST: 'h',
      SMTP_PORT: '587',
      SMTP_USER: 'u',
      SMTP_PASSWORD: 'p',
      EMAIL_RECIPIENTS: 'r',
    };
    expect(pickNotificationEnv(all)).toEqual(all);
  });

  it('omits keys the form never filled rather than sending empty strings', () => {
    expect(pickNotificationEnv({ SMTP_HOST: 'h' })).toEqual({ SMTP_HOST: 'h' });
  });
});
