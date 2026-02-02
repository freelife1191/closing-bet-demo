
import CryptoJS from 'crypto-js';

const SECRET_KEY = process.env.NEXT_PUBLIC_STORAGE_SECRET || 'closing-bet-demo-secret-key';

export const SecureStorage = {
  encrypt: (data: string): string => {
    try {
      return CryptoJS.AES.encrypt(data, SECRET_KEY).toString();
    } catch (e) {
      console.error("Encryption failed", e);
      return "";
    }
  },

  decrypt: (cipherText: string): string => {
    try {
      const bytes = CryptoJS.AES.decrypt(cipherText, SECRET_KEY);
      return bytes.toString(CryptoJS.enc.Utf8);
    } catch (e) {
      console.error("Decryption failed", e);
      return "";
    }
  },

  setItem: (key: string, value: string) => {
    if (typeof window === 'undefined') return;
    const encrypted = SecureStorage.encrypt(value);
    sessionStorage.setItem(key, encrypted);
  },

  getItem: (key: string): string | null => {
    if (typeof window === 'undefined') return null;
    const encrypted = sessionStorage.getItem(key);
    if (!encrypted) return null;
    return SecureStorage.decrypt(encrypted);
  },

  removeItem: (key: string) => {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem(key);
  }
};
