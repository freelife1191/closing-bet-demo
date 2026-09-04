/**
 * `/api/system/env` returns secrets masked (`sk-1***…***abcd`). The mask still
 * leaks the first and last four characters, and a password input renders its
 * placeholder in plain text, so we show a fixed sentence instead: the field
 * only needs to say that a key is stored, not which one.
 *
 * Both key fields go through this one function so they cannot drift apart.
 */
const STORED_KEY_HINT = '저장되어 있습니다. 바꾸려면 새 값을 입력하세요';

export function apiKeyFieldProps(
  stored: string | undefined,
  hint: string
): { value: string; placeholder: string } {
  if (stored && stored.includes('*')) {
    return { value: '', placeholder: STORED_KEY_HINT };
  }
  return { value: stored || '', placeholder: hint };
}

/**
 * Keys the notification test is allowed to save before sending.
 *
 * That request posts before the user has pressed Save, so anything it carries
 * is written to the server's .env without consent. Sending the whole envVars
 * object would let an API key cleared in another tab disappear on a test send.
 */
const NOTIFICATION_ENV_KEYS = [
  'TELEGRAM_BOT_TOKEN',
  'TELEGRAM_CHAT_ID',
  'DISCORD_WEBHOOK_URL',
  'SMTP_HOST',
  'SMTP_PORT',
  'SMTP_USER',
  'SMTP_PASSWORD',
  'EMAIL_RECIPIENTS',
];

export function pickNotificationEnv(
  envVars: Record<string, string>
): Record<string, string> {
  return Object.fromEntries(
    NOTIFICATION_ENV_KEYS.filter((key) => key in envVars).map((key) => [key, envVars[key]])
  );
}
