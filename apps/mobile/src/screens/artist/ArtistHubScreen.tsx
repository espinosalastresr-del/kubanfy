import React, {useEffect, useState} from 'react';
import {StyleSheet, Text, View} from 'react-native';

import {apiRequest} from '../../api/client';
import {colors, radius, spacing, typography} from '../../theme/tokens';
import {ModeSwitcher} from '../../components/ModeSwitcher';
import {Button} from '../../ui/Button';
import {Screen} from '../../ui/Screen';
import {ArtistUploadScreen} from './ArtistUploadScreen';

type Artist = {
  id: string;
  name: string;
  slug: string;
  verified: boolean;
  status: string;
};

export function ArtistHubScreen() {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploadFor, setUploadFor] = useState<Artist | null>(null);
  const [createName, setCreateName] = useState('');

  const load = async () => {
    try {
      const data = await apiRequest<Artist[]>('/v1/artist/mine');
      setArtists(data);
      setError(null);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'No tienes acceso de artista o el servidor rechazó la petición',
      );
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (uploadFor) {
    return (
      <ArtistUploadScreen
        artistId={uploadFor.id}
        artistName={uploadFor.name}
        onBack={() => setUploadFor(null)}
        onUploaded={() => {
          setUploadFor(null);
          load();
        }}
      />
    );
  }

  const createArtist = async () => {
    const name = createName.trim() || 'Mi proyecto';
    try {
      await apiRequest('/v1/artist', {
        method: 'POST',
        body: JSON.stringify({name, country: 'CU'}),
      });
      setCreateName('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo crear el artista');
    }
  };

  return (
    <Screen scroll>
      <Text style={styles.title}>Portal artista</Text>
      <Text style={styles.sub}>
        Publica y gestiona tu catálogo. Los permisos se validan siempre en el servidor.
      </Text>
      <ModeSwitcher />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {artists.map(a => (
        <View key={a.id} style={styles.card}>
          <Text style={styles.cardTitle}>{a.name}</Text>
          <Text style={styles.meta}>
            @{a.slug} · {a.verified ? 'Verificado' : 'Sin verificar'} · {a.status}
          </Text>
          <Button
            title="Subir pista"
            onPress={() => setUploadFor(a)}
            style={styles.btn}
          />
        </View>
      ))}

      {!artists.length ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>Crear perfil de artista</Text>
          <Text style={styles.emptyBody}>
            Si tu cuenta tiene rol ARTIST o eres el primer perfil, puedes crear
            tu página aquí.
          </Text>
          <Button title="Crear artista" onPress={createArtist} style={styles.btn} />
          <Button title="Actualizar" variant="secondary" onPress={load} />
        </View>
      ) : null}
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
  error: {color: colors.danger, marginBottom: spacing.md},
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  cardTitle: {...typography.subtitle, color: colors.text},
  meta: {...typography.caption, color: colors.textSecondary, marginTop: 4},
  btn: {marginTop: spacing.md},
  emptyCard: {
    backgroundColor: colors.bgElevated,
    borderRadius: radius.lg,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.border,
  },
  emptyTitle: {...typography.subtitle, color: colors.text},
  emptyBody: {
    ...typography.caption,
    color: colors.textMuted,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
});
