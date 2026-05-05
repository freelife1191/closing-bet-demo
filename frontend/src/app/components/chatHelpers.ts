export const STORED_MODEL_KEY = 'chatbot_current_model';

export function shouldSendOnEnter(
  key: string,
  shiftKey: boolean,
  isComposing: boolean
): boolean {
  if (key !== 'Enter') return false;
  if (shiftKey) return false;
  if (isComposing) return false;
  return true;
}

export function getStoredModel(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const value = window.localStorage.getItem(STORED_MODEL_KEY);
    return value && value.trim().length > 0 ? value : null;
  } catch {
    return null;
  }
}

export function setStoredModel(model: string | null | undefined): void {
  if (typeof window === 'undefined') return;
  try {
    if (model && model.trim().length > 0) {
      window.localStorage.setItem(STORED_MODEL_KEY, model);
    } else {
      window.localStorage.removeItem(STORED_MODEL_KEY);
    }
  } catch {
    // ignore quota / privacy errors
  }
}
