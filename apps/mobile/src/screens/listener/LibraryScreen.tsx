import React, {useCallback, useState} from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';
import {useFocusEffect} from '@react-navigation/native';

import {queueDownload, processQueue} from '../../offline/downloadService';
import {listDownloadJobs, listOfflineTracks} from '../../offline/storage';
import {DownloadJob, OfflineTrackMeta} from '../../offline/types';
import {usePlayerStore} from '../../store/playerStore';
import {colors, radius, spacing, typography} from '../../theme/tokens';
import {ModeSwitcher} from '../../components/ModeSwitcher';
import {Button} from '../../ui/Button';
import {Screen} from '../../ui/Screen';

export function LibraryScreen() {
  const [offline, setOffline] = useState<OfflineTrackMeta[]>([]);
  const [jobs, setJobs] = useState<DownloadJob[]>([]);
  const playTrack = usePlayerStore(s => s.playTrack);

  const refresh = useCallback(async () => {
    setOffline(await listOfflineTracks());
    setJobs(await listDownloadJobs());
  }, []);

  useFocusEffect(
    useCallback(() => {
      refresh();
      processQueue().finally(refresh);
    }, [refresh]),
  );

  return (
    <Screen scroll>
      <Text style={styles.title}>Biblioteca offline</Text>
      <Text style={styles.sub}>
        Las descargas quedan en el dispositivo. Sin red puedes reproducir lo ya
        guardado. Cache temporal ≠ descarga permanente (plan offline-first).
      </Text>
      <ModeSwitcher />

      <Text style={styles.section}>Descargado</Text>
      {offline.map(t => (
        <Pressable
          key={`${t.trackId}-${t.quality}`}
          style={styles.row}
          onPress={() =>
            playTrack({
              trackId: t.trackId,
              title: t.title,
              quality: t.quality,
            })
          }>
          <View style={styles.rowBody}>
            <Text style={styles.rowTitle}>{t.title}</Text>
            <Text style={styles.meta}>
              {t.quality.toUpperCase()} ·{' '}
              {t.localUri.startsWith('http') ? 'URL guardada' : 'Archivo local'}
            </Text>
          </View>
          <Text style={styles.play}>▶</Text>
        </Pressable>
      ))}
      {!offline.length ? (
        <Text style={styles.empty}>Aún no hay pistas offline.</Text>
      ) : null}

      <Text style={[styles.section, {marginTop: spacing.xl}]}>Cola</Text>
      {jobs
        .filter(j => j.status !== 'completed')
        .map(j => (
          <View key={j.id} style={styles.row}>
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>{j.title}</Text>
              <Text style={styles.meta}>
                {j.status} · {Math.round(j.progress * 100)}%
                {j.error ? ` · ${j.error}` : ''}
              </Text>
            </View>
          </View>
        ))}

      <Button
        title="Reintentar cola"
        variant="secondary"
        onPress={async () => {
          await processQueue();
          await refresh();
        }}
        style={{marginTop: spacing.lg}}
      />

      <Button
        title="Demo: encolar descarga de ejemplo"
        variant="ghost"
        onPress={async () => {
          await queueDownload({
            trackId: '00000000-0000-0000-0000-000000000001',
            title: 'Demo track (requiere ID real)',
            quality: 'medium',
          });
          await refresh();
        }}
        style={{marginTop: spacing.sm}}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {...typography.title, color: colors.text, marginTop: spacing.lg},
  sub: {
    ...typography.caption,
    color: colors.textMuted,
    marginBottom: spacing.lg,
    lineHeight: 18,
  },
  section: {...typography.subtitle, color: colors.text, marginBottom: spacing.md},
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
  rowBody: {flex: 1},
  rowTitle: {...typography.bodyBold, color: colors.text},
  meta: {...typography.micro, color: colors.textMuted, marginTop: 2},
  play: {color: colors.primary, fontSize: 18, paddingHorizontal: spacing.sm},
  empty: {...typography.caption, color: colors.textMuted},
});
