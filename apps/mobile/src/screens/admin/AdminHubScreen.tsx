import React, {useEffect, useState} from 'react';
import {StyleSheet, Text, View} from 'react-native';

import {apiRequest} from '../../api/client';
import {colors, radius, spacing, typography} from '../../theme/tokens';
import {ModeSwitcher} from '../../components/ModeSwitcher';
import {Button} from '../../ui/Button';
import {Screen} from '../../ui/Screen';

type Flag = {key: string; enabled: boolean; description?: string | null};

/**
 * Admin surface inside the same binary.
 * Security model:
 * - UI is merely a convenience; every call hits RBAC-protected API routes.
 * - Users without admin roles never receive data (403).
 * - Prefer step-up / reason on destructive actions (suspend, takedown) — server logs audit.
 */
export function AdminHubScreen() {
  const [flags, setFlags] = useState<Flag[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await apiRequest<Flag[]>('/v1/admin/feature-flags');
      setFlags(data);
      setError(null);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Sin permisos de administración o API no disponible',
      );
      setFlags([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <Screen scroll>
      <Text style={styles.title}>Administración</Text>
      <Text style={styles.sub}>
        Panel operativo en la misma app. La autorización real vive en el API (RBAC + audit log).
      </Text>
      <ModeSwitcher />

      {error ? (
        <View style={styles.warn}>
          <Text style={styles.warnText}>{error}</Text>
        </View>
      ) : null}

      <Text style={styles.section}>Feature flags</Text>
      {flags.map(f => (
        <View key={f.key} style={styles.row}>
          <View style={styles.rowBody}>
            <Text style={styles.rowTitle}>{f.key}</Text>
            {f.description ? (
              <Text style={styles.meta}>{f.description}</Text>
            ) : null}
          </View>
          <View
            style={[
              styles.pill,
              {backgroundColor: f.enabled ? colors.success : colors.bgInput},
            ]}>
            <Text style={styles.pillText}>{f.enabled ? 'ON' : 'OFF'}</Text>
          </View>
        </View>
      ))}

      <Button title="Actualizar" variant="secondary" onPress={load} style={styles.btn} />
      <Text style={styles.footnote}>
        Moderación, pagos y suspensión de usuarios se conectarán a las rutas
        /v1/admin/* y /v1/payments/admin/* ya expuestas por el backend.
      </Text>
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
  section: {
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
  rowBody: {flex: 1},
  rowTitle: {...typography.bodyBold, color: colors.text},
  meta: {...typography.micro, color: colors.textMuted, marginTop: 2},
  pill: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
  },
  pillText: {...typography.micro, color: colors.text, fontWeight: '700'},
  btn: {marginTop: spacing.lg},
  warn: {
    backgroundColor: colors.primarySoft,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.lg,
  },
  warnText: {...typography.caption, color: colors.primary},
  footnote: {
    ...typography.micro,
    color: colors.textMuted,
    marginTop: spacing.xl,
    lineHeight: 16,
  },
});
