import {create} from 'zustand';

import {apiRequest} from '../api/client';
import {getOfflineTrack} from '../offline/storage';
import {PlayerTrack} from '../offline/types';
import {trackEvent} from '../offline/analytics';
import {
  enginePause,
  enginePlay,
  engineResume,
  engineSeek,
  engineStop,
  setupPlayerEngine,
  subscribeEngine,
} from '../player/trackPlayerService';

type PlayerState = {
  current: PlayerTrack | null;
  queue: PlayerTrack[];
  isPlaying: boolean;
  positionSec: number;
  durationSec: number;
  isBuffering: boolean;
  error: string | null;
  engineNative: boolean | null;

  initEngine: () => Promise<void>;
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
  seek: (sec: number) => void;
};

let engineSubscribed = false;

export const usePlayerStore = create<PlayerState>((set, get) => ({
  current: null,
  queue: [],
  isPlaying: false,
  positionSec: 0,
  durationSec: 0,
  isBuffering: false,
  error: null,
  engineNative: null,

  initEngine: async () => {
    const {native} = await setupPlayerEngine();
    set({engineNative: native});
    if (!engineSubscribed) {
      engineSubscribed = true;
      subscribeEngine((status, positionSec, durationSec) => {
        set(s => ({
          isPlaying: status === 'playing',
          isBuffering: status === 'loading',
          positionSec: positionSec ?? s.positionSec,
          durationSec: durationSec ?? s.durationSec,
        }));
      });
    }
  },

  playTrack: async ({trackId, title, artistName, quality = 'medium'}) => {
    set({isBuffering: true, error: null});
    try {
      await get().initEngine();

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
        await enginePlay(track);
        await trackEvent('play_start', {
          track_id: trackId,
          offline: true,
          quality,
        });
        return;
      }

      let uri: string | undefined;
      try {
        const preview = await apiRequest<{url?: string; available?: boolean}>(
          '/v1/music/preview',
          {
            method: 'POST',
            body: JSON.stringify({track_id: trackId, quality}),
          },
        );
        uri = preview.url;
      } catch {
        // fallback download endpoint
      }
      if (!uri) {
        const dl = await apiRequest<{url?: string; signed_url?: string}>(
          '/v1/music/download',
          {
            method: 'POST',
            body: JSON.stringify({track_id: trackId, quality}),
          },
        );
        uri = dl.url || dl.signed_url;
      }
      if (!uri) {
        throw new Error('No se pudo obtener URL de reproducción');
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
      await enginePlay(track);
      await trackEvent('play_start', {
        track_id: trackId,
        offline: false,
        quality,
      });
    } catch (e) {
      set({
        isBuffering: false,
        isPlaying: false,
        error: e instanceof Error ? e.message : 'Error de reproducción',
      });
    }
  },

  togglePlay: () => {
    const {isPlaying, current} = get();
    if (!current) {
      return;
    }
    if (isPlaying) {
      get().pause();
    } else {
      get().resume();
    }
  },

  pause: () => {
    set({isPlaying: false});
    enginePause().catch(() => {});
  },

  resume: () => {
    if (!get().current) {
      return;
    }
    set({isPlaying: true});
    engineResume().catch(() => {});
  },

  stop: () => {
    set({
      isPlaying: false,
      current: null,
      positionSec: 0,
      durationSec: 0,
    });
    engineStop().catch(() => {});
  },

  setPosition: (sec: number) => set({positionSec: sec}),

  seek: (sec: number) => {
    set({positionSec: sec});
    engineSeek(sec).catch(() => {});
  },
}));
