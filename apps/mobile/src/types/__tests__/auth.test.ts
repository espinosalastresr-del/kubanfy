import {canAccessAdmin, canAccessArtist, deriveModes} from '../auth';

describe('deriveModes', () => {
  it('always includes listener', () => {
    expect(deriveModes([])).toEqual(['listener']);
  });

  it('adds artist for ARTIST role', () => {
    expect(deriveModes(['USER', 'ARTIST'])).toEqual(['listener', 'artist']);
  });

  it('adds admin for SUPER_ADMIN', () => {
    const modes = deriveModes(['SUPER_ADMIN']);
    expect(modes).toContain('listener');
    expect(modes).toContain('admin');
  });

  it('canAccess helpers', () => {
    expect(canAccessAdmin(['MODERATOR'])).toBe(true);
    expect(canAccessAdmin(['USER'])).toBe(false);
    expect(canAccessArtist(['ARTIST_MANAGER'])).toBe(true);
    expect(canAccessArtist(['USER'])).toBe(false);
  });
});
