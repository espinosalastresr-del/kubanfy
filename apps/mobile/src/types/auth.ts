/**
 * Roles from API. Server is source of truth.
 * Client only uses these to show/hide navigation sections.
 */

export type SystemRole =
  | 'SUPER_ADMIN'
  | 'ADMIN'
  | 'SUPPORT'
  | 'MODERATOR'
  | 'FINANCE'
  | 'ANALYST'
  | 'ARTIST'
  | 'ARTIST_MANAGER'
  | 'USER';

export type UserMe = {
  id: string;
  email: string;
  display_name: string | null;
  country: string;
  status: string;
  roles: string[];
};

export type LoginResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserMe;
};

/** App "mode" derived from roles — UI only */
export type AppMode = 'listener' | 'artist' | 'admin';

export function deriveModes(roles: string[]): AppMode[] {
  const modes: AppMode[] = ['listener'];
  const upper = roles.map(r => r.toUpperCase());
  if (upper.some(r => r === 'ARTIST' || r === 'ARTIST_MANAGER')) {
    modes.push('artist');
  }
  if (
    upper.some(r =>
      ['SUPER_ADMIN', 'ADMIN', 'SUPPORT', 'MODERATOR', 'FINANCE', 'ANALYST'].includes(r),
    )
  ) {
    modes.push('admin');
  }
  return modes;
}

export function canAccessAdmin(roles: string[]): boolean {
  return deriveModes(roles).includes('admin');
}

export function canAccessArtist(roles: string[]): boolean {
  return deriveModes(roles).includes('artist');
}
