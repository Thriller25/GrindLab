const TOKEN_KEY = "grindlab_token";

export const getAccessToken = (): string | null => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setAccessToken = (token: string): void => {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // ignore storage issues (e.g. private mode)
  }
};

export const clearAuth = (): void => {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage issues (e.g. private mode)
  }
};

export const hasAuth = (): boolean => Boolean(getAccessToken());

export const authProvider = {
  getAccessToken,
  setAccessToken,
  clearAuth,
  hasAuth,
};

export default authProvider;
