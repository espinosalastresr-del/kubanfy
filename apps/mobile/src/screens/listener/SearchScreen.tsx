import React, {useCallback, useState} from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import {apiRequest} from '../../api/client';
import {queueDownload} from '../../offline/downloadService';
import {usePlayerStore} from '../../store/playerStore';
import {colors, radius, spacing, typography} from '../../theme/tokens';
import {ModeSwitcher} from '../../components/ModeSwitcher';
import {TextField} from '../../ui/TextField';
import {Screen} from '../../ui/Screen';

type SearchHit = {
  provider: string;
  provider_track_id: string;
  title: string;
  artists: string[];
  album?: string | null;
  duration?: number | null;
  artwork?: string | null;
  track_id?: string;
};

export function SearchScreen() {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const playTrack = usePlayerStore(s => s.playTrack);

  const search = useCallback(async () => {
    const query = q.trim();
    if (query.length < 1) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<SearchHit[]>(
        `/v1/music/search?q=${encodeURIComponent(query)}&limit=30`,
        {auth: false},
      );
      setHits(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error de búsqueda');
      setHits([]);
    } finally {
      setLoading(false);
    }
  }, [q]);

  const onPlay = async (item: SearchHit) => {
    // Prefer catalog track_id when present; else play via provider resolve path
    if (item.track_id) {
      await playTrack({
        trackId: item.track_id,
        title: item.title,
        artistName: item.artists?.[0],
      });
      return;
    }
    // Provider-only result: hit update then play when we have track_id
    try {
      const updated = await apiRequest<{
        track_id?: string;
        title: string;
        artists: string[];
      }>('/v1/music/update', {
        method: 'POST',
        auth: false,
        body: JSON.stringify({
          provider: item.provider,
          provider_track_id: item.provider_track_id,
        }),
      });
      if (updated.track_id) {
        await playTrack({
          trackId: updated.track_id,
          title: updated.title || item.title,
          artistName: updated.artists?.[0] || item.artists?.[0],
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo reproducir');
    }
  };

  return (
    <Screen>
      <Text style={styles.title}>Buscar</Text>
      <ModeSwitcher />
      <TextField
        label="Canción, artista…"
        value={q}
        onChangeText={setQ}
        onSubmitEditing={search}
        returnKeyType="search"
        placeholder="Guantanamera, Buena Vista…"
        autoCorrect={false}
      />
      <Pressable style={styles.searchBtn} onPress={search}>
        {loading ? (
          <ActivityIndicator color={colors.text} />
        ) : (
          <Text style={styles.searchBtnText}>Buscar</Text>
        )}
      </Pressable>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        data={hits}
        keyExtractor={(item, i) =>
          `${item.provider}:${item.provider_track_id}:${i}`
        }
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        ListEmptyComponent={
          !loading ? (
            <Text style={styles.empty}>
              Escribe y busca en el catálogo y proveedores.
            </Text>
          ) : null
        }
        renderItem={({item}) => (
          <Pressable
            style={styles.row}
            onPress={() => onPlay(item)}
            onLongPress={() => {
              if (item.track_id) {
                queueDownload({
                  trackId: item.track_id,
                  title: item.title,
                  quality: 'medium',
                });
              }
            }}>
            <View style={styles.art}>
              <Text style={styles.artText}>{item.title.slice(0, 1)}</Text>
            </View>
            <View style={styles.body}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {item.title}
              </Text>
              <Text style={styles.meta} numberOfLines={1}>
                {(item.artists || []).join(', ') || 'Artista'} · {item.provider}
              </Text>
            </View>
            <Text style={styles.play}>▶</Text>
          </Pressable>
        )}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {...typography.title, color: colors.text, marginTop: spacing.lg},
  searchBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  searchBtnText: {...typography.bodyBold, color: colors.text},
  error: {color: colors.danger, marginBottom: spacing.sm},
  list: {paddingBottom: 120},
  empty: {...typography.caption, color: colors.textMuted, marginTop: spacing.lg},
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
  art: {
    width: 44,
    height: 44,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  artText: {color: colors.primary, fontWeight: '700'},
  body: {flex: 1},
  rowTitle: {...typography.bodyBold, color: colors.text},
  meta: {...typography.micro, color: colors.textMuted, marginTop: 2},
  play: {color: colors.primary, fontSize: 16, paddingHorizontal: spacing.sm},
});
