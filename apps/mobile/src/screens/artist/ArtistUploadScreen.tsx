/**
 * Artist track upload — multipart to POST /v1/artist/{id}/tracks/upload
 * Requires react-native-document-picker when native modules are linked.
 * Falls back to guided instructions if the module is unavailable.
 */

import React, {useState} from 'react';
import {Alert, StyleSheet, Text, View} from 'react-native';

import {getAccessToken} from '../../api/client';
import {colors, radius, spacing, typography} from '../../theme/tokens';
import {Button} from '../../ui/Button';
import {Screen} from '../../ui/Screen';
import {TextField} from '../../ui/TextField';

type Props = {
  artistId: string;
  artistName: string;
  onUploaded?: () => void;
  onBack?: () => void;
};

function getBaseUrl(): string {
  return (
    (globalThis as {KUBANFY_API_URL?: string}).KUBANFY_API_URL ||
    'http://10.0.2.2:8000'
  );
}

export function ArtistUploadScreen({
  artistId,
  artistName,
  onUploaded,
  onBack,
}: Props) {
  const [title, setTitle] = useState('');
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileUri, setFileUri] = useState<string | null>(null);
  const [fileType, setFileType] = useState<string>('audio/mpeg');
  const [acceptLicense, setAcceptLicense] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const pickFile = async () => {
    try {
      // Dynamic require so JS bundle works before native link
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const DocumentPicker = require('react-native-document-picker').default;
      const res = await DocumentPicker.pickSingle({
        type: [DocumentPicker.types.audio, DocumentPicker.types.allFiles],
        copyTo: 'cachesDirectory',
      });
      setFileName(res.name || 'audio');
      setFileUri(res.fileCopyUri || res.uri);
      setFileType(res.type || 'audio/mpeg');
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes('cancel') || msg.includes('Cancel')) {
        return;
      }
      setError(
        'Selector de archivos no disponible aún. Ejecuta bootstrap:native e instala react-native-document-picker.',
      );
    }
  };

  const upload = async () => {
    if (!title.trim()) {
      setError('Título requerido');
      return;
    }
    if (!acceptLicense) {
      setError('Debes aceptar la licencia de distribución');
      return;
    }
    if (!fileUri || !fileName) {
      setError('Selecciona un archivo de audio');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const token = await getAccessToken();
      const form = new FormData();
      form.append('title', title.trim());
      form.append('accept_license', acceptLicense ? 'true' : 'false');
      form.append('explicit', 'false');
      form.append('language', 'es');
      form.append('file', {
        uri: fileUri,
        name: fileName,
        type: fileType,
      } as unknown as Blob);

      const res = await fetch(
        `${getBaseUrl()}/v1/artist/${artistId}/tracks/upload`,
        {
          method: 'POST',
          headers: {
            Authorization: token ? `Bearer ${token}` : '',
            Accept: 'application/json',
            // Content-Type set automatically for multipart
          },
          body: form,
        },
      );

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.error?.message || `Upload falló (${res.status})`,
        );
      }

      setResult(
        `Subido. track_id=${data.track_id} status=${data.status}` +
          (data.job_id ? ` job=${data.job_id}` : ''),
      );
      Alert.alert('Listo', 'Pista enviada. El transcode corre en background.');
      onUploaded?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error de upload');
    } finally {
      setLoading(false);
    }
  };

  const publish = async () => {
    // Publish requires track_id from last upload — parse if present
    const match = result?.match(/track_id=([0-9a-f-]{36})/i);
    if (!match) {
      setError('Sube una pista primero para publicar');
      return;
    }
    const trackId = match[1];
    setLoading(true);
    try {
      const token = await getAccessToken();
      const res = await fetch(
        `${getBaseUrl()}/v1/artist/${artistId}/tracks/${trackId}/publish`,
        {
          method: 'POST',
          headers: {
            Authorization: token ? `Bearer ${token}` : '',
            Accept: 'application/json',
          },
        },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.error?.message || `Publish falló (${res.status})`);
      }
      setResult(`Publicado. track_id=${trackId} status=${data.status}`);
      Alert.alert('Publicado', 'La pista ya está en el catálogo.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al publicar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen scroll>
      <Text style={styles.title}>Subir pista</Text>
      <Text style={styles.sub}>
        {artistName} · El servidor valida audio (FFprobe), guarda master y
        encola transcode.
      </Text>

      <TextField
        label="Título"
        value={title}
        onChangeText={setTitle}
        placeholder="Nombre de la canción"
      />

      <Button
        title={fileName ? `Archivo: ${fileName}` : 'Elegir audio'}
        variant="secondary"
        onPress={pickFile}
        style={styles.btn}
      />

      <Button
        title={
          acceptLicense
            ? '✓ Licencia aceptada'
            : 'Acepto licencia de distribución'
        }
        variant={acceptLicense ? 'primary' : 'ghost'}
        onPress={() => setAcceptLicense(!acceptLicense)}
        style={styles.btn}
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {result ? <Text style={styles.ok}>{result}</Text> : null}

      <Button title="Subir" onPress={upload} loading={loading} style={styles.btn} />
      <Button
        title="Publicar última subida"
        variant="secondary"
        onPress={publish}
        loading={loading}
        style={styles.btn}
      />
      {onBack ? (
        <Button title="Volver" variant="ghost" onPress={onBack} />
      ) : null}

      <View style={styles.note}>
        <Text style={styles.noteText}>
          Formatos típicos: WAV, FLAC, MP3. El API rechaza archivos inválidos.
          No se confía en metadatos del cliente para autorización.
        </Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {...typography.title, color: colors.text, marginTop: spacing.lg},
  sub: {
    ...typography.caption,
    color: colors.textMuted,
    marginBottom: spacing.xl,
    lineHeight: 18,
  },
  btn: {marginBottom: spacing.md},
  error: {color: colors.danger, marginBottom: spacing.md},
  ok: {color: colors.success, marginBottom: spacing.md, ...typography.caption},
  note: {
    marginTop: spacing.lg,
    padding: spacing.md,
    backgroundColor: colors.bgElevated,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  noteText: {...typography.micro, color: colors.textMuted, lineHeight: 16},
});
