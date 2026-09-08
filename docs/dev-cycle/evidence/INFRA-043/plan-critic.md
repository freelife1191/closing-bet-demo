# Plan Critic — 2026-09-09 notification settings

## Verdict

OKAY, with the required clarifications below before implementation. The plan covers the previously identified six contract gaps: disabled notification gating, facade bool propagation, secret-safe logs/responses, partial env-save results, send-after-save ordering, and Next upstream error handling.

## Evidence checked

- `engine/messenger.py` currently drops `_send_*` return values and has custom sender exception logs.
- `engine/messenger_senders.py` currently logs exception text and does not check `config.disabled`.
- `app/routes/common_notification_routes.py` currently treats `_send_platform_test_notification()` as success regardless of sender result.
- `app/routes/common_update_routes.py` currently ignores `update_env_file()` results.
- `frontend/src/app/components/SettingsModal.tsx` currently sends notification after env POST without checking `res.ok` or `status`.
- `frontend/src/app/api/system/env/route.ts` currently lacks a catch around the upstream fetch and response body read.

## Required clarifications

1. For INFRA-043, implement the `503` disabled result at the notification route boundary (or an explicitly equivalent contract). A sender-level `False` alone cannot distinguish disabled from transport failure, so the route must inspect the Messenger configuration or receive a typed result before choosing 503 versus 502.
2. Preserve legacy facade method compatibility explicitly: `_send_telegram`, `_send_discord`, and `_send_email` should return `bool`, and all callers must be checked for `None` assumptions. Custom sender helpers must also return a meaningful bool if they remain in scope.
3. Apply secret-safe logging to every notification exception path named in the plan, including `Messenger` custom Telegram/Discord methods, notifier wrappers, sender exceptions, and the outer route catch. Route responses must use fixed messages and never `str(error)`.
4. For INFRA-051, define behavior for `update_env_file()` file-write exceptions separately from rejected input. Rejected input may partially apply allowed values and return 400; an atomic write failure must leave both file and `os.environ` unchanged and return a server error.
5. In FE-041, require the save response body to be valid JSON with `status: "ok"`; a 2xx body with `status: "error"` or malformed JSON must make zero notification requests. Require notification success to include both HTTP success and `status: "success"`.
6. For the Next route's fixed 502 response, preserve `Cache-Control: no-store` on both upstream fetch failures and response-body read failures, and keep the response JSON shape stable for SettingsModal.
7. The plan's illustrative `response.json[...]` should be implemented with the repository's actual Flask test API (`get_json()`), and tests must assert no secret values appear in response bodies, logs, or frontend-visible error text.
8. The final browser QA must use an isolated fake account and transport doubles only. It must prove request ordering (env POST completes successfully before notification POST), zero notification calls on every save failure class, disabled 503 behavior, sender false→502 behavior, and admin/non-admin access. It must not exercise real notification endpoints or real `.env`/`data`.

No architectural blocker was found. With these clarifications recorded in the execution notes or implementation tasks, the plan is ready for implementation.
