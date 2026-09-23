import React, {useCallback, useState} from 'react';
import {
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {useFocusEffect} from '@react-navigation/native';

import {apiRequest} from '../../api/client';
import {colors, radius, spacing, typography} from '../../theme/tokens';
import {ModeSwitcher} from '../../components/ModeSwitcher';
import {Button} from '../../ui/Button';
import {Screen} from '../../ui/Screen';
import {TextField} from '../../ui/TextField';

type Playlist = {
  id: string;
  name: string;
  description?: string | null;
  visibility: string;
  created_at: string;
};

type Fav = {
  id: string;
  target_type: string;
  target_id: string;
  created_at: string;
};

export function PlaylistsScreen() {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [favorites, setFavorites] = useState<Fav[]>([]);
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      const [pls, favs] = await Promise.all([
        apiRequest<Playlist[]>('/v1/playlists'),
        apiRequest<Fav[]>('/v1/favorites'),
      ]);
      setPlaylists(pls);
      setFavorites(favs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar');
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const create = async () => {
    const n = name.trim();
    if (!n) {
      return;
    }
    setCreating(true);
    try {
      await apiRequest('/v1/playlists', {
        method: 'POST',
        body: JSON.stringify({name: n, visibility: 'private'}),
      });
      setName('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo crear');
    } finally {
      setCreating(false);
    }
  };

  const remove = (pl: Playlist) => {
    Alert.alert('Eliminar playlist', `¿Borrar “${pl.name}”?`, [
      {text: 'Cancelar', style: 'cancel'},
      {
        text: 'Eliminar',
        style: 'destructive',
        onPress: async () => {
          try {
            await apiRequest(`/v1/playlists/${pl.id}`, {method: 'DELETE'});
            await load();
          } catch (e) {
            setError(e instanceof Error ? e.message : 'Error al borrar');
          }
        },
      },
    ]);
  };

  return (
    <Screen>
      <Text style={styles.title}>Playlists</Text>
      <Text style={styles.sub}>Tus listas y favoritos sincronizados con el API.</Text>
      <ModeSwitcher />

      <View style={styles.createRow}>
        <View style={styles.createField}>
          <TextField
            label="Nueva playlist"
            value={name}
            onChangeText={setName}
            placeholder="Nombre"
          />
        </View>
        <Button
          title="Crear"
          onPress={create}
          loading={creating}
          style={styles.createBtn}
        />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Text style={styles.section}>Mis listas</Text>
      <FlatList
        data={playlists}
        keyExtractor={item => item.id}
        style={{flexGrow: 0}}
        ListEmptyComponent={
          <Text style={styles.empty}>No tienes playlists todavía.</Text>
        }
        renderItem={({item}) => (
          <Pressable
            style={styles.row}
            onLongPress={() => remove(item)}
            delayLongPress={400}>
            <View style={styles.icon}>
              <Text style={styles.iconText}>♫</Text>
            </View>
            <View style={styles.body}>
              <Text style={styles.rowTitle}>{item.name}</Text>
              <Text style={styles.meta}>
                {item.visibility === 'public' ? 'Pública' : 'Privada'}
              </Text>
            </View>
          </Pressable>
        )}
      />

      <Text style={[styles.section, {marginTop: spacing.xl}]}>Favoritos</Text>
      <FlatList
        data={favorites}
        keyExtractor={item => item.id}
        contentContainerStyle={{paddingBottom: 120}}
        ListEmptyComponent={
          <Text style={styles.empty}>Sin favoritos aún.</Text>
        }
        renderItem={({item}) => (
          <View style={styles.row}>
            <View style={[styles.icon, {backgroundColor: colors.accentSoft}]}>
              <Text style={[styles.iconText, {color: colors.accent}]}>♥</Text>
            </View>
            <View style={styles.body}>
              <Text style={styles.rowTitle}>
                {item.target_type} · {item.target_id.slice(0, 8)}…
              </Text>
              <Text style={styles.meta}>
                {new Date(item.created_at).toLocaleDateString()}
              </Text>
            </View>
          </View>
        )}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {...typography.title, color: colors.text, marginTop: spacing.lg},
  sub: {
    ...typography.caption,
    color: colors.textMuted,
    marginBottom: spacing.md,
  },
  createRow: {marginBottom: spacing.sm},
  createField: {},
  createBtn: {marginTop: -spacing.sm, marginBottom: spacing.md},
  error: {color: colors.danger, marginBottom: spacing.sm},
  section: {
    ...typography.subtitle,
    color: colors.text,
    marginBottom: spacing.md,
  },
  empty: {...typography.caption, color: colors.textMuted, marginBottom: spacing.md},
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
  icon: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  iconText: {color: colors.primary, fontSize: 16},
  body: {flex: 1},
  rowTitle: {...typography.bodyBold, color: colors.text},
  meta: {...typography.micro, color: colors.textMuted, marginTop: 2},
});
