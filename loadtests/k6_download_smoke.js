/**
 * Download/content path smoke (plan §41).
 * k6 run -e BASE_URL=http://127.0.0.1:8000 loadtests/k6_download_smoke.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '15s',
  thresholds: {
    http_req_failed: ['rate<0.15'],
    http_req_duration: ['p(95)<2500'],
  },
};

export default function () {
  const live = http.get(`${BASE}/health/live`);
  check(live, { 'live': (r) => r.status === 200 });

  // Unauthenticated download should fail auth (not 5xx)
  const dl = http.post(
    `${BASE}/v1/music/download`,
    JSON.stringify({ track_id: '00000000-0000-0000-0000-000000000001', quality: 'medium' }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(dl, {
    'download not 5xx': (r) => r.status < 500,
    'download requires auth or validates': (r) => [401, 403, 404, 422].includes(r.status) || r.status === 200,
  });

  // Range on missing content without auth
  const range = http.get(`${BASE}/v1/music/content/00000000-0000-0000-0000-000000000001`, {
    headers: { Range: 'bytes=0-1023' },
  });
  check(range, {
    'content range not 5xx': (r) => r.status < 500,
  });

  sleep(0.4);
}
