import React from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';

import {useAuthStore} from '../store/authStore';
import {AppMode} from '../types/auth';
import {colors, radius, spacing, typography} from '../theme/tokens';

const LABELS: Record<AppMode, string> = {
  listener: 'Escuchar',
  artist: 'Artista',
  admin: 'Admin',
};

const ACCENTS: Record<AppMode, string> = {
  listener: colors.roleListener,
  artist: colors.roleArtist,
  admin: colors.roleAdmin,
};

/**
 * Mode switcher is UI-only. Server RBAC still gates every admin/artist API call.
 * Destructive admin actions should re-check permissions server-side (already do).
 */
export function ModeSwitcher() {
  const modes = useAuthStore(s => s.modes);
  const active = useAuthStore(s => s.activeMode);
  const setMode = useAuthStore(s => s.setMode);

  if (modes.length < 2) {
    return null;
  }

  return (
    <View style={styles.wrap}>
      {modes.map(m => {
        const selected = m === active;
        return (
          <Pressable
            key={m}
            onPress={() => setMode(m)}
            style={[
              styles.chip,
              selected && {backgroundColor: ACCENTS[m], borderColor: ACCENTS[m]},
            ]}>
            <Text style={[styles.label, selected && styles.labelActive]}>
              {LABELS[m]}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.xl,
    backgroundColor: colors.bgElevated,
    borderRadius: radius.lg,
    padding: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chip: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'transparent',
  },
  label: {...typography.caption, color: colors.textSecondary, fontWeight: '600'},
  labelActive: {color: colors.text},
});
