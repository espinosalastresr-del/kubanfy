/**
 * KubanFy load smoke (plan §41).
 *
 * Requires k6: https://k6.io
 * Usage:
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 loadtests/k6_smoke.js
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 -e VUS=20 -e DURATION=60s loadtests/k6_smoke.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const failRate = new Rate('failed_requests');

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const VUS = Number(__ENV.VUS || 10);
const DURATION = __ENV.DURATION || '30s';

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<1500'],
    failed_requests: ['rate<0.05'],
  },
};

export default function () {
  const live = http.get(`${BASE}/health/live`);
  const okLive = check(live, {
    'live 200': (r) => r.status === 200,
  });
  failRate.add(!okLive);

  const ready = http.get(`${BASE}/health/ready`);
  check(ready, {
    'ready 200 or 503': (r) => r.status === 200 || r.status === 503,
  });

  // Unauthenticated root should not 500
  const root = http.get(`${BASE}/v1/`);
  check(root, {
    'api root not 5xx': (r) => r.status < 500,
  });

  sleep(0.3);
}
