/**
 * Optional authenticated smoke (plan §41).
 * k6 run -e BASE_URL=http://127.0.0.1:8000 -e EMAIL=a@b.c -e PASSWORD=secret loadtests/k6_auth_smoke.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const EMAIL = __ENV.EMAIL || '';
const PASSWORD = __ENV.PASSWORD || '';

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '20s',
  thresholds: {
    http_req_failed: ['rate<0.1'],
    http_req_duration: ['p(95)<2000'],
  },
};

export default function () {
  const live = http.get(`${BASE}/health/live`);
  check(live, { 'live 200': (r) => r.status === 200 });

  if (EMAIL && PASSWORD) {
    const res = http.post(
      `${BASE}/v1/auth/login`,
      JSON.stringify({ email: EMAIL, password: PASSWORD }),
      { headers: { 'Content-Type': 'application/json' } },
    );
    check(res, {
      'login 200 or 401': (r) => r.status === 200 || r.status === 401,
      'login not 5xx': (r) => r.status < 500,
    });
    if (res.status === 200) {
      const body = res.json();
      const token = body.access_token;
      if (token) {
        const me = http.get(`${BASE}/v1/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        check(me, { 'me 200': (r) => r.status === 200 });
      }
    }
  }
  sleep(0.5);
}
