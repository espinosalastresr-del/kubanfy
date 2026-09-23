import {create} from 'zustand';

import {apiRequest} from '../api/client';
import {getOfflineTrack} from '../offline/storage';
import {PlayerTrack} from '../offline/types';
import {trackEvent} from '../offline/analytics';

type PlayerState = {
  current: PlayerTrack | null;
  queue: PlayerTrack[];
  isPlaying: boolean;
  positionSec: number;
  durationSec: number;
  isBuffering: boolean;
  error: string | null;

  playTrack: (track: {
    trackId: string;
    title: string;
    artistName?: string;
    quality?: 'low' | 'medium' | 'lossless';
  }) => Promise<void>;
  togglePlay: () => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  setPosition: (sec: number) => void;
  setDuration: (sec: number) => void;
};

/**
 * Player state machine. Actual audio engine (react-native-track-player)
 * hooks into these flags once native modules are linked.
 */
export const usePlayerStore = create<PlayerState>((set, get) => ({
  current: null,
  queue: [],
  isPlaying: false,
  positionSec: 0,
  durationSec: 0,
  isBuffering: false,
  error: null,

  playTrack: async ({trackId, title, artistName, quality = 'medium'}) => {
    set({isBuffering: true, error: null});
    try {
      // Prefer offline copy
      const offline = await getOfflineTrack(trackId, quality);
      if (offline?.localUri) {
        const track: PlayerTrack = {
          trackId,
          title: offline.title || title,
          artistName,
          uri: offline.localUri,
          duration: offline.duration,
          isLocal: true,
          quality: offline.quality,
        };
        set({
          current: track,
          isPlaying: true,
          isBuffering: false,
          positionSec: 0,
          durationSec: offline.duration || 0,
        });
        await trackEvent('play_start', {
          track_id: trackId,
          offline: true,
          quality,
        });
        return;
      }

      // Online: request signed URL / stream endpoint
      let uri: string | undefined;
      try {
        const preview = await apiRequest<{url?: string; available?: boolean}>(
          '/v1/music/preview',
          {
            method: 'POST',
            body: JSON.stringify({track_id: trackId}),
          },
        );
        uri = preview.url;
      } catch {
        const dl = await apiRequest<{url?: string}>(
          '/v1/music/download',
          {
            method: 'POST',
            body: JSON.stringify({track_id: trackId, quality}),
          },
        );
        uri = dl.url;
      }

      if (!uri) {
        throw new Error('No hay URL de reproducción disponible');
      }

      const track: PlayerTrack = {
        trackId,
        title,
        artistName,
        uri,
        isLocal: false,
        quality,
      };
      set({
        current: track,
        isPlaying: true,
        isBuffering: false,
        positionSec: 0,
      });
      await trackEvent('play_start', {
        track_id: trackId,
        offline: false,
        quality,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Error de reproducción';
      set({isBuffering: false, isPlaying: false, error: message});
    }
  },

  togglePlay: () => {
    const {isPlaying, current} = get();
    if (!current) {
      return;
    }
    set({isPlaying: !isPlaying});
  },

  pause: () => set({isPlaying: false}),
  resume: () => {
    if (get().current) {
      set({isPlaying: true});
    }
  },
  stop: () =>
    set({
      isPlaying: false,
      current: null,
      positionSec: 0,
      durationSec: 0,
    }),
  setPosition: sec => set({positionSec: sec}),
  setDuration: sec => set({durationSec: sec}),
}));
