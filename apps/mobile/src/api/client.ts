/**
 * KubanFy API client.
 * Authorization always comes from server-issued tokens.
 * Roles returned by /auth/me are for UI only — never for security decisions.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Keychain from 'react-native-keychain';

const TOKEN_KEY = 'kubanfy.access_token';
const REFRESH_KEY = 'kubanfy.refresh_token';
const DEVICE_KEY = 'kubanfy.device_id';
const AUTH_KEYCHAIN_SERVICE = 'com.kubanfy.auth';
const DEVICE_KEYCHAIN_SERVICE = 'com.kubanfy.device';
const OFFLINE_USER_KEYCHAIN_SERVICE = 'com.kubanfy.offline-user';

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

export async function getDeviceId(): Promise<string> {
  const credentials = await Keychain.getGenericPassword({service: DEVICE_KEYCHAIN_SERVICE});
  if (credentials) {
    return credentials.username;
  }
  const legacy = await AsyncStorage.getItem(DEVICE_KEY);
  const id =
    legacy || `rn-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  await Keychain.setGenericPassword(id, 'device', {
    service: DEVICE_KEYCHAIN_SERVICE,
    accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  if (legacy) {
    await AsyncStorage.removeItem(DEVICE_KEY);
  }
  return id;
}

export async function setOfflineUserId(userId: string): Promise<void> {
  await Keychain.setGenericPassword('user', userId, {
    service: OFFLINE_USER_KEYCHAIN_SERVICE,
    accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export async function getOfflineUserId(): Promise<string | null> {
  try {
    const credentials = await Keychain.getGenericPassword({service: OFFLINE_USER_KEYCHAIN_SERVICE});
    return credentials?.password || null;
  } catch {
    return null;
  }
}

export async function clearOfflineUserId(): Promise<void> {
  await Keychain.resetGenericPassword({service: OFFLINE_USER_KEYCHAIN_SERVICE});
}

export async function setTokens(access: string, refresh: string): Promise<void> {
  await Keychain.setGenericPassword(
    access,
    refresh,
    {
      service: AUTH_KEYCHAIN_SERVICE,
      accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    },
  );
}

async function getCredentials(): Promise<Keychain.UserCredentials | null> {
  try {
    const credentials = await Keychain.getGenericPassword({service: AUTH_KEYCHAIN_SERVICE});
    return credentials || null;
  } catch {
    return null;
  }
}

export async function clearTokens(): Promise<void> {
  await Keychain.resetGenericPassword({service: AUTH_KEYCHAIN_SERVICE});
}

export async function getAccessToken(): Promise<string | null> {
  const credentials = await getCredentials();
  return credentials?.username || null;
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
