import React from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';

import {usePlayerStore} from '../store/playerStore';
import {colors, radius, shadows, spacing, typography} from '../theme/tokens';

export function MiniPlayer() {
  const current = usePlayerStore(s => s.current);
  const isPlaying = usePlayerStore(s => s.isPlaying);
  const isBuffering = usePlayerStore(s => s.isBuffering);
  const togglePlay = usePlayerStore(s => s.togglePlay);
  const stop = usePlayerStore(s => s.stop);
  const error = usePlayerStore(s => s.error);

  if (!current && !error) {
    return null;
  }

  return (
    <View style={[styles.bar, shadows.player]}>
      <View style={styles.art}>
        <Text style={styles.artText}>
          {(current?.title || '?').slice(0, 1).toUpperCase()}
        </Text>
      </View>
      <View style={styles.meta}>
        <Text style={styles.title} numberOfLines={1}>
          {current?.title || 'Error'}
        </Text>
        <Text style={styles.sub} numberOfLines={1}>
          {error
            ? error
            : isBuffering
              ? 'Cargando…'
              : current?.isLocal
                ? 'Offline'
                : current?.artistName || 'Streaming'}
        </Text>
      </View>
      <Pressable
        onPress={togglePlay}
        style={styles.btn}
        accessibilityRole="button"
        accessibilityLabel={isPlaying ? 'Pausar' : 'Reproducir'}>
        <Text style={styles.btnText}>{isPlaying ? '❚❚' : '▶'}</Text>
      </Pressable>
      <Pressable onPress={stop} style={styles.btn} accessibilityLabel="Detener">
        <Text style={styles.btnText}>✕</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.lg,
    backgroundColor: colors.glass,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  art: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  artText: {color: colors.primary, fontWeight: '700', fontSize: 16},
  meta: {flex: 1, marginRight: spacing.sm},
  title: {...typography.bodyBold, color: colors.text},
  sub: {...typography.micro, color: colors.textMuted, marginTop: 2},
  btn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnText: {color: colors.text, fontSize: 16},
});
