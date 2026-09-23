/**
 * Audio engine abstraction (plan §47 offline playback).
 *
 * Prefer react-native-track-player when native modules are linked.
 * Falls back to a no-op JS engine that still drives UI state so the app
 * remains testable without android/ios folders.
 */

import type {OfflineTrackMeta, PlayerTrack} from '../offline/types';
import {decryptOfflineFile} from '../offline/offlineCrypto';
import {verifyOfflineLicense} from '../offline/offlineLicenseVerifier';
import {getDeviceId, getOfflineUserId} from '../api/client';

export type EngineStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'stopped' | 'error';

type Listener = (status: EngineStatus, positionSec?: number, durationSec?: number) => void;

let listeners: Listener[] = [];
let currentUri: string | null = null;
let status: EngineStatus = 'idle';
let useNative = false;
let nativeReady = false;
let ephemeralPlaybackPath: string | null = null;

function emit(s: EngineStatus, positionSec?: number, durationSec?: number) {
  status = s;
  listeners.forEach(l => l(s, positionSec, durationSec));
}

async function tryLoadNative(): Promise<boolean> {
  if (nativeReady) {
    return useNative;
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const {Capability, State, Event} = require('react-native-track-player');

    await TrackPlayer.setupPlayer({waitForBuffer: true});
    await TrackPlayer.updateOptions({
      capabilities: [
        Capability.Play,
        Capability.Pause,
        Capability.Stop,
        Capability.SeekTo,
      ],
      compactCapabilities: [Capability.Play, Capability.Pause],
      progressUpdateEventInterval: 1,
    });

    TrackPlayer.addEventListener(Event.PlaybackState, (e: {state: unknown}) => {
      const st = e.state;
      if (st === State.Playing) {
        emit('playing');
      } else if (st === State.Paused) {
        emit('paused');
      } else if (st === State.Stopped || st === State.None) {
        emit('stopped');
      } else if (st === State.Buffering || st === State.Connecting) {
        emit('loading');
      }
    });

    TrackPlayer.addEventListener(
      Event.PlaybackProgressUpdated,
      (e: {position: number; duration: number}) => {
        emit(status === 'playing' ? 'playing' : status, e.position, e.duration);
      },
    );

    useNative = true;
    nativeReady = true;
    return true;
  } catch {
    useNative = false;
    nativeReady = true;
    return false;
  }
}

export async function cleanupOfflinePlaybackTemps(): Promise<void> {
  try {
    const RNFS = require('react-native-fs');
    const dir = `${RNFS.DocumentDirectoryPath}/kubanfy/offline`;
    if (!(await RNFS.exists(dir))) return;
    const entries = await RNFS.readDir(dir);
    await Promise.all(
      entries
        .filter((entry: {name: string}) =>
          entry.name.endsWith('.playback') ||
          entry.name.endsWith('.playback.part') ||
          entry.name.endsWith('.kfy.part') ||
          entry.name.endsWith('.meta.part'),
        )
        .map((entry: {path: string}) =>
          RNFS.unlink(entry.path).catch(() => undefined),
        ),
    );
  } catch {
    // Best-effort cleanup; an unavailable filesystem must not block startup.
  }
}

export async function setupPlayerEngine(): Promise<{native: boolean}> {
  await cleanupOfflinePlaybackTemps();
  const native = await tryLoadNative();
  return {native};
}

export function subscribeEngine(listener: Listener): () => void {
  listeners.push(listener);
  return () => {
    listeners = listeners.filter(l => l !== listener);
  };
}

export async function enginePlay(track: PlayerTrack): Promise<void> {
  await tryLoadNative();
  currentUri = track.uri;
  emit('loading');

  if (useNative) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    await TrackPlayer.reset();
    await TrackPlayer.add({
      id: track.trackId,
      url: track.uri,
      title: track.title,
      artist: track.artistName || 'KubanFy',
      duration: track.duration,
    });
    await TrackPlayer.play();
    emit('playing', 0, track.duration || 0);
    return;
  }

  emit('playing', 0, track.duration || 0);
}

export async function enginePause(): Promise<void> {
  if (useNative) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    await TrackPlayer.pause();
  }
  emit('paused');
}

export async function engineResume(): Promise<void> {
  if (useNative) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    await TrackPlayer.play();
  }
  emit('playing');
}

async function cleanupEphemeralPlayback(): Promise<void> {
  if (!ephemeralPlaybackPath) return;
  try {
    const RNFS = require('react-native-fs');
    if (await RNFS.exists(ephemeralPlaybackPath)) await RNFS.unlink(ephemeralPlaybackPath);
  } catch {
    // Best-effort cleanup; startup cleanup should remove stale files.
  }
  ephemeralPlaybackPath = null;
}

export async function engineStop(): Promise<void> {
  if (useNative) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    await TrackPlayer.stop();
    await TrackPlayer.reset();
  }
  currentUri = null;
  await cleanupEphemeralPlayback();
  emit('stopped', 0);
}

export async function engineSeek(sec: number): Promise<void> {
  if (useNative) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    await TrackPlayer.seekTo(sec);
  }
  emit(status, sec);
}

export function getEngineStatus(): EngineStatus {
  return status;
}

export function getCurrentUri(): string | null {
  return currentUri;
}

export async function registerPlaybackService(): Promise<void> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    TrackPlayer.registerPlaybackService(() =>
      require('./playbackService').playbackService,
    );
  } catch {
    // not linked
  }
}


/**
 * Materializes one encrypted offline asset into an ephemeral playback file.
 * The plaintext is kept only for the active playback session and is removed
 * when engineStop() is called (and should also be cleaned at app startup).
 */
export async function enginePlayOffline(track: OfflineTrackMeta): Promise<void> {
  const RNFS = await (async () => require('react-native-fs'))();
  await cleanupEphemeralPlayback();
  const encryptedPath = track.localUri.replace(/^file:\/\//, '');
  const userId = await getOfflineUserId();
  if (!userId) throw new Error('Offline playback requires a signed-in account');
  verifyOfflineLicense(track.offlineLicense || '', {
    trackId: track.trackId,
    quality: track.quality,
    deviceId: await getDeviceId(),
    userId,
    contentHash: track.contentHash,
  });
  const outputPath = encryptedPath + '.playback';
  await decryptOfflineFile({
    RNFS,
    encryptedPath,
    metadataPath: encryptedPath + '.meta',
    outputPath,
    trackId: track.trackId,
    quality: track.quality,
    contentHash: track.contentHash,
  });
  ephemeralPlaybackPath = outputPath;
  await enginePlay({
    trackId: track.trackId,
    title: track.title,
    artistName: track.artistName,
    uri: outputPath.startsWith('file://') ? outputPath : 'file://' + outputPath,
    duration: track.duration,
    isLocal: true,
    quality: track.quality,
  });
}
