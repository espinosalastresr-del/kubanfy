/**
 * Offline-capable analytics: queue when offline, flush when online.
 */

import NetInfo from '@react-native-community/netinfo';

import {apiRequest} from '../api/client';
import {drainAnalyticsQueue, enqueueAnalytics} from './storage';

function uuid(): string {
  return `evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function trackEvent(
  event_type: string,
  metadata: Record<string, unknown> = {},
): Promise<void> {
  const event_id = uuid();
  const payload = {
    event_type,
    event_id,
    metadata,
    platform: 'mobile',
  };

  const net = await NetInfo.fetch();
  if (!net.isConnected) {
    await enqueueAnalytics({
      event_id,
      event_type,
      payload,
      createdAt: Date.now(),
    });
    return;
  }

  try {
    await apiRequest('/v1/analytics/events', {
      method: 'POST',
      body: JSON.stringify(payload),
      auth: true,
    });
  } catch {
    await enqueueAnalytics({
      event_id,
      event_type,
      payload,
      createdAt: Date.now(),
    });
  }
}

export async function flushAnalyticsQueue(): Promise<number> {
  const net = await NetInfo.fetch();
  if (!net.isConnected) {
    return 0;
  }
  const events = await drainAnalyticsQueue();
  if (!events.length) {
    return 0;
  }
  try {
    await apiRequest('/v1/analytics/events/batch', {
      method: 'POST',
      body: JSON.stringify({
        events: events.map(e => ({
          event_type: e.event_type,
          event_id: e.event_id,
          metadata: e.payload.metadata,
          platform: 'mobile',
        })),
      }),
    });
    return events.length;
  } catch {
    // re-queue on failure
    for (const e of events) {
      await enqueueAnalytics(e);
    }
    return 0;
  }
}

/** Call once at app start */
export function startAnalyticsSync(): () => void {
  const unsub = NetInfo.addEventListener(state => {
    if (state.isConnected) {
      flushAnalyticsQueue().catch(() => {});
    }
  });
  flushAnalyticsQueue().catch(() => {});
  return unsub;
}
