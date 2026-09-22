import React, {useState} from 'react';
import {KeyboardAvoidingView, Platform, StyleSheet, Text, View} from 'react-native';

import {useAuthStore} from '../../store/authStore';
import {colors, spacing, typography} from '../../theme/tokens';
import {Button} from '../../ui/Button';
import {Screen} from '../../ui/Screen';
import {TextField} from '../../ui/TextField';

export function LoginScreen() {
  const login = useAuthStore(s => s.login);
  const register = useAuthStore(s => s.register);
  const isLoading = useAuthStore(s => s.isLoading);
  const error = useAuthStore(s => s.error);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');

  const onSubmit = async () => {
    if (mode === 'login') {
      await login(email.trim(), password);
    } else {
      await register(email.trim(), password, name.trim() || undefined);
    }
  };

  return (
    <Screen scroll>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.inner}>
        <View style={styles.brand}>
          <Text style={styles.logo}>KubanFy</Text>
          <Text style={styles.tagline}>Música cubana. Offline. Tuya.</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.heading}>
            {mode === 'login' ? 'Bienvenido' : 'Crear cuenta'}
          </Text>
          <Text style={styles.sub}>
            Una sola app para escuchar, publicar y administrar — según tu cuenta.
          </Text>

          {mode === 'register' ? (
            <TextField
              label="Nombre"
              value={name}
              onChangeText={setName}
              autoCapitalize="words"
              placeholder="Tu nombre"
            />
          ) : null}

          <TextField
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            placeholder="tu@email.com"
          />
          <TextField
            label="Contraseña"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="••••••••"
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button
            title={mode === 'login' ? 'Entrar' : 'Registrarme'}
            onPress={onSubmit}
            loading={isLoading}
            style={styles.cta}
          />

          <Button
            title={
              mode === 'login'
                ? '¿No tienes cuenta? Regístrate'
                : '¿Ya tienes cuenta? Entra'
            }
            variant="ghost"
            onPress={() => setMode(mode === 'login' ? 'register' : 'login')}
          />
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  inner: {flex: 1, justifyContent: 'center', paddingTop: spacing.xxxl},
  brand: {marginBottom: spacing.xxl, alignItems: 'center'},
  logo: {...typography.hero, color: colors.primary},
  tagline: {...typography.body, color: colors.textSecondary, marginTop: spacing.sm},
  card: {
    backgroundColor: colors.bgElevated,
    borderRadius: 20,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.border,
  },
  heading: {...typography.title, color: colors.text, marginBottom: spacing.sm},
  sub: {
    ...typography.caption,
    color: colors.textMuted,
    marginBottom: spacing.xl,
    lineHeight: 18,
  },
  error: {
    ...typography.caption,
    color: colors.danger,
    marginBottom: spacing.md,
  },
  cta: {marginTop: spacing.sm, marginBottom: spacing.md},
});
