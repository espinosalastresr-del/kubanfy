import React, {useEffect, useState} from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';

import {apiRequest} from '../../api/client';
import {useAuthStore} from '../../store/authStore';
import {colors, radius, spacing, typography} from '../../theme/tokens';
import {Screen} from '../../ui/Screen';
import {ModeSwitcher} from '../../components/ModeSwitcher';
import {usePlayerStore} from '../../store/playerStore';
import {queueDownload} from '../../offline/downloadService';

type HomePayload = {
  country?: string;
  local_artists?: {id: string; name: string; verified?: boolean}[];
  top_50_country?: {rank: number; title?: string; track_id: string; score?: number}[];
  new_releases?: {id: string; title: string}[];
};

export function ListenerHomeScreen() {
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);
  const playTrack = usePlayerStore(s => s.playTrack);
  const [home, setHome] = useState<HomePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiRequest<HomePayload>('/v1/discovery/home');
        if (!cancelled) {
          setHome(data);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'No se pudo cargar');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Screen scroll>
      <View style={styles.header}>
        <View>
          <Text style={styles.hello}>Hola{user?.display_name ? `, ${user.display_name}` : ''}</Text>
          <Text style={styles.sub}>Descubre música cerca de ti</Text>
        </View>
        <Pressable onPress={() => logout()} hitSlop={12}>
          <Text style={styles.logout}>Salir</Text>
        </Pressable>
      </View>

      <ModeSwitcher />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Section title="Artistas locales">
        {(home?.local_artists || []).slice(0, 6).map(a => (
          <View key={a.id} style={styles.row}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{a.name.slice(0, 1)}</Text>
            </View>
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>{a.name}</Text>
              {a.verified ? <Text style={styles.badge}>Verificado</Text> : null}
            </View>
          </View>
        ))}
        {!home?.local_artists?.length && !error ? (
          <Text style={styles.empty}>Pronto verás artistas de tu país aquí.</Text>
        ) : null}
      </Section>

      <Section title="Top del momento">
        {(home?.top_50_country || []).slice(0, 8).map(t => (
          <Pressable
            key={String(t.track_id)}
            style={styles.row}
            onPress={() =>
              playTrack({
                trackId: String(t.track_id),
                title: t.title || 'Track',
              })
            }
            onLongPress={() =>
              queueDownload({
                trackId: String(t.track_id),
                title: t.title || 'Track',
                quality: 'medium',
              })
            }>
            <Text style={styles.rank}>{t.rank}</Text>
            <Text style={styles.rowTitle}>{t.title || 'Track'}</Text>
          </Pressable>
        ))}
      </Section>

      <Section title="Novedades">
        {(home?.new_releases || []).slice(0, 6).map(t => (
          <View key={t.id} style={styles.chip}>
            <Text style={styles.chipText}>{t.title}</Text>
          </View>
        ))}
      </Section>
    </Screen>
  );
}

function Section({title, children}: {title: string; children: React.ReactNode}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginTop: spacing.lg,
    marginBottom: spacing.lg,
  },
  hello: {...typography.title, color: colors.text},
  sub: {...typography.caption, color: colors.textMuted, marginTop: 4},
  logout: {...typography.caption, color: colors.primary},
  error: {color: colors.danger, marginBottom: spacing.md},
  section: {marginBottom: spacing.xl},
  sectionTitle: {
    ...typography.subtitle,
    color: colors.text,
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  avatarText: {color: colors.primary, fontWeight: '700'},
  rowBody: {flex: 1},
  rowTitle: {...typography.bodyBold, color: colors.text, flex: 1},
  badge: {...typography.micro, color: colors.accent, marginTop: 2},
  rank: {
    width: 28,
    ...typography.bodyBold,
    color: colors.primary,
  },
  chip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.bgElevated,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipText: {...typography.caption, color: colors.text},
  empty: {...typography.caption, color: colors.textMuted},
});
