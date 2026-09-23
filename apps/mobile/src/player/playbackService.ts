/**
 * Headless playback service for react-native-track-player (Android).
 */

export async function playbackService() {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const TrackPlayer = require('react-native-track-player');
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const {Event} = require('react-native-track-player');

    TrackPlayer.addEventListener(Event.RemotePlay, () => TrackPlayer.play());
    TrackPlayer.addEventListener(Event.RemotePause, () => TrackPlayer.pause());
    TrackPlayer.addEventListener(Event.RemoteStop, () => TrackPlayer.stop());
    TrackPlayer.addEventListener(Event.RemoteSeek, (e: {position: number}) => {
      TrackPlayer.seekTo(e.position);
    });
  } catch {
    // module missing
  }
}
