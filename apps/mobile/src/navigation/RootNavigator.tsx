import React, {useEffect} from 'react';
import {ActivityIndicator, StyleSheet, View} from 'react-native';
import {NavigationContainer, DarkTheme} from '@react-navigation/native';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';

import {useAuthStore} from '../store/authStore';
import {colors} from '../theme/tokens';
import {LoginScreen} from '../screens/auth/LoginScreen';
import {ListenerHomeScreen} from '../screens/listener/HomeScreen';
import {LibraryScreen} from '../screens/listener/LibraryScreen';
import {SearchScreen} from '../screens/listener/SearchScreen';
import {PlaylistsScreen} from '../screens/listener/PlaylistsScreen';
import {ArtistHubScreen} from '../screens/artist/ArtistHubScreen';
import {AdminHubScreen} from '../screens/admin/AdminHubScreen';
import {MiniPlayer} from '../components/MiniPlayer';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

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

function ListenerTabs() {
  return (
    <View style={{flex: 1}}>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarStyle: {
            backgroundColor: colors.bgElevated,
            borderTopColor: colors.border,
            height: 58,
            paddingBottom: 6,
            paddingTop: 4,
          },
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarLabelStyle: {fontSize: 11, fontWeight: '600'},
        }}>
        <Tab.Screen
          name="Discover"
          component={ListenerHomeScreen}
          options={{tabBarLabel: 'Inicio'}}
        />
        <Tab.Screen
          name="Search"
          component={SearchScreen}
          options={{tabBarLabel: 'Buscar'}}
        />
        <Tab.Screen
          name="Playlists"
          component={PlaylistsScreen}
          options={{tabBarLabel: 'Listas'}}
        />
        <Tab.Screen
          name="Library"
          component={LibraryScreen}
          options={{tabBarLabel: 'Offline'}}
        />
      </Tab.Navigator>
      <MiniPlayer />
    </View>
  );
}

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
          <Stack.Screen name="Listener" component={ListenerTabs} />
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
