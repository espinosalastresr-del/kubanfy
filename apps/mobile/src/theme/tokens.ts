/**
 * KubanFy design tokens — modern, native-feeling, Cuba-inspired.
 * Dark-first (listening at night / low data screens).
 */

export const colors = {
  // Brand
  primary: '#E63946', // warm carmine / Cuban flag red
  primaryMuted: '#C1121F',
  primarySoft: 'rgba(230, 57, 70, 0.15)',
  accent: '#F4A261', // warm amber
  accentSoft: 'rgba(244, 162, 97, 0.18)',

  // Surfaces (dark)
  bg: '#0B0D10',
  bgElevated: '#14181F',
  bgCard: '#1A1F28',
  bgInput: '#222833',
  border: '#2A3140',
  borderFocus: '#E63946',

  // Text
  text: '#F5F7FA',
  textSecondary: '#A0A8B8',
  textMuted: '#6B7385',
  textInverse: '#0B0D10',

  // Semantic
  success: '#2DD4A8',
  warning: '#F4A261',
  danger: '#FF5C5C',
  info: '#5B8DEF',

  // Role accents
  roleListener: '#E63946',
  roleArtist: '#F4A261',
  roleAdmin: '#5B8DEF',

  // Overlays
  overlay: 'rgba(0, 0, 0, 0.55)',
  glass: 'rgba(26, 31, 40, 0.85)',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
} as const;

export const typography = {
  hero: {fontSize: 32, fontWeight: '700' as const, letterSpacing: -0.5},
  title: {fontSize: 22, fontWeight: '700' as const, letterSpacing: -0.3},
  subtitle: {fontSize: 17, fontWeight: '600' as const},
  body: {fontSize: 15, fontWeight: '400' as const},
  bodyBold: {fontSize: 15, fontWeight: '600' as const},
  caption: {fontSize: 13, fontWeight: '400' as const},
  label: {fontSize: 12, fontWeight: '600' as const, letterSpacing: 0.4},
  micro: {fontSize: 11, fontWeight: '500' as const},
} as const;

export const shadows = {
  card: {
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.25,
    shadowRadius: 12,
    elevation: 6,
  },
  player: {
    shadowColor: '#000',
    shadowOffset: {width: 0, height: -2},
    shadowOpacity: 0.35,
    shadowRadius: 16,
    elevation: 12,
  },
} as const;
