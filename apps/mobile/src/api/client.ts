/**
 * KubanFy API client.
 * Authorization always comes from server-issued tokens.
 * Roles returned by /auth/me are for UI only — never for security decisions.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const TOKEN_KEY = 'kubanfy.access_token';
const REFRESH_KEY = 'kubanfy.refresh_token';
const DEVICE_KEY = 'kubanfy.device_id';

export type ApiErrorBody = {
  error?: {code?: string; message?: string; details?: Record<string, unknown>};
};

function getBaseUrl(): string {
  // Override via env at build time or AsyncStorage in debug settings
  return (
    (globalThis as {KUBANFY_API_URL?: string}).KUBANFY_API_URL ||
    'http://10.0.2.2:8000' // Android emulator → host machine
  );
}

async function getDeviceId(): Promise<string> {
  let id = await AsyncStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = `rn-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    await AsyncStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export async function setTokens(access: string, refresh: string): Promise<void> {
  await AsyncStorage.multiSet([
    [TOKEN_KEY, access],
    [REFRESH_KEY, refresh],
  ]);
}

export async function clearTokens(): Promise<void> {
  await AsyncStorage.multiRemove([TOKEN_KEY, REFRESH_KEY]);
}

export async function getAccessToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & {auth?: boolean} = {},
): Promise<T> {
  const {auth = true, headers: extraHeaders, ...rest} = options;
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'X-Device-ID': await getDeviceId(),
    ...(extraHeaders as Record<string, string>),
  };

  if (auth) {
    const token = await getAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${getBaseUrl()}${path}`, {
    ...rest,
    headers,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const body = data as ApiErrorBody;
    const err = new Error(body.error?.message || `HTTP ${res.status}`) as Error & {
      status?: number;
      code?: string;
    };
    err.status = res.status;
    err.code = body.error?.code;
    throw err;
  }

  return data as T;
}
