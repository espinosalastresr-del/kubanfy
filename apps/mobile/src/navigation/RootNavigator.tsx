import React, {useEffect} from 'react';
import {ActivityIndicator, StyleSheet, View} from 'react-native';
import {NavigationContainer, DarkTheme} from '@react-navigation/native';
import {createNativeStackNavigator} from '@react-navigation/native-stack';

import {useAuthStore} from '../store/authStore';
import {colors} from '../theme/tokens';
import {LoginScreen} from '../screens/auth/LoginScreen';
import {ListenerHomeScreen} from '../screens/listener/HomeScreen';
import {ArtistHubScreen} from '../screens/artist/ArtistHubScreen';
import {AdminHubScreen} from '../screens/admin/AdminHubScreen';

const Stack = createNativeStackNavigator();

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.bg,
    card: colors.bgElevated,
    text: colors.text,
    border: colors.border,
    primary: colors.primary,
  },
};

export function RootNavigator() {
  const isHydrated = useAuthStore(s => s.isHydrated);
  const user = useAuthStore(s => s.user);
  const activeMode = useAuthStore(s => s.activeMode);
  const hydrate = useAuthStore(s => s.hydrate);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  if (!isHydrated) {
    return (
      <View style={styles.boot}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator screenOptions={{headerShown: false, animation: 'fade'}}>
        {!user ? (
          <Stack.Screen name="Login" component={LoginScreen} />
        ) : activeMode === 'artist' ? (
          <Stack.Screen name="Artist" component={ArtistHubScreen} />
        ) : activeMode === 'admin' ? (
          <Stack.Screen name="Admin" component={AdminHubScreen} />
        ) : (
          <Stack.Screen name="Home" component={ListenerHomeScreen} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
