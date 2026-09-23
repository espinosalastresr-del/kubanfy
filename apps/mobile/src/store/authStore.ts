import {create} from 'zustand';

import {
  apiRequest,
  clearOfflineUserId,
  clearTokens,
  setOfflineUserId,
  setTokens,
} from '../api/client';
import {
  AppMode,
  LoginResponse,
  UserMe,
  canAccessAdmin,
  canAccessArtist,
  deriveModes,
} from '../types/auth';

type AuthState = {
  user: UserMe | null;
  modes: AppMode[];
  activeMode: AppMode;
  isHydrated: boolean;
  isLoading: boolean;
  error: string | null;

  hydrate: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  setMode: (mode: AppMode) => void;
  refreshMe: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  modes: ['listener'],
  activeMode: 'listener',
  isHydrated: false,
  isLoading: false,
  error: null,

  hydrate: async () => {
    try {
      const me = await apiRequest<UserMe>('/v1/auth/me');
      const modes = deriveModes(me.roles || []);
      const active = get().activeMode;
      set({
        user: me,
        modes,
        activeMode: modes.includes(active) ? active : modes[0],
        isHydrated: true,
      });
    } catch {
      await clearTokens();
      set({user: null, modes: ['listener'], activeMode: 'listener', isHydrated: true});
    }
  },

  login: async (email, password) => {
    set({isLoading: true, error: null});
    try {
      const data = await apiRequest<LoginResponse>('/v1/auth/login', {
        method: 'POST',
        auth: false,
        body: JSON.stringify({email, password}),
      });
      await setTokens(data.access_token, data.refresh_token);
      await setOfflineUserId(data.user.id);
      const modes = deriveModes(data.user.roles || []);
      set({
        user: data.user,
        modes,
        activeMode: modes[0],
        isLoading: false,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Error de inicio de sesión';
      set({isLoading: false, error: msg});
      throw e;
    }
  },

  register: async (email, password, displayName) => {
    set({isLoading: true, error: null});
    try {
      await apiRequest('/v1/auth/register', {
        method: 'POST',
        auth: false,
        body: JSON.stringify({
          email,
          password,
          display_name: displayName || undefined,
          country: 'CU',
        }),
      });
      await get().login(email, password);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Error de registro';
      set({isLoading: false, error: msg});
      throw e;
    }
  },

  logout: async () => {
    try {
      await apiRequest('/v1/auth/logout', {method: 'POST'});
    } catch {
      // ignore
    }
    await clearTokens();
    await clearOfflineUserId();
    set({user: null, modes: ['listener'], activeMode: 'listener', error: null});
  },

  setMode: mode => {
    const {modes} = get();
    if (!modes.includes(mode)) {
      return;
    }
    // Extra gate: never enter admin/artist without role claim (UI only)
    const roles = get().user?.roles || [];
    if (mode === 'admin' && !canAccessAdmin(roles)) {
      return;
    }
    if (mode === 'artist' && !canAccessArtist(roles)) {
      return;
    }
    set({activeMode: mode});
  },

  refreshMe: async () => {
    const me = await apiRequest<UserMe>('/v1/auth/me');
    const modes = deriveModes(me.roles || []);
    const active = get().activeMode;
    set({
      user: me,
      modes,
      activeMode: modes.includes(active) ? active : modes[0],
    });
  },
}));
