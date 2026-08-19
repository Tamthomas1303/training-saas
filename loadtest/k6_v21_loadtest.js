// k6 load test — Training SaaS v2.1
//
// Muc tieu: mo phong 10 -> 35 -> 50 nguoi dung dong thoi trong ~8 phut, tap trung vao
// GET /api/dashboard/overview/ (man Dashboard tong hop CEO/GDDT) - endpoint tung bi OOM
// tren Render truoc khi sua (xem commit "fix: sua OOM man Dashboard tong hop").
// Cac endpoint khac (kpi/report, employees list, auth/me) duoc goi xen ke de mo phong
// 1 phien lam viec that (dang nhap -> mo dashboard -> xem bao cao KPI -> tim nhan su),
// khong chi ban rieng 1 endpoint.
//
// KHONG hardcode URL/mat khau that trong file nay - tat ca truyen qua -e (bien moi truong k6).
//
// Cach chay (xem chi tiet trong loadtest/README.md):
//   k6 run -e BASE_URL="https://<ten-service>.onrender.com/api" \
//          -e TEST_USER_PREFIX="k6_test_" -e TEST_USER_COUNT=5 \
//          -e TEST_PASSWORD="<mat khau tai khoan test>" \
//          loadtest/k6_v21_loadtest.js
//
// Tai khoan test: tao truoc bang `python manage.py create_loadtest_users` (idempotent).

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.1.0/index.js';

// ===== Cau hinh qua bien moi truong (-e KEY=value), khong sua cung o day =====
const BASE_URL = (__ENV.BASE_URL || '').replace(/\/+$/, '');
const LOGIN_PATH = __ENV.LOGIN_PATH || '/auth/login/';
const TEST_USER_PREFIX = __ENV.TEST_USER_PREFIX || 'k6_test_';
const TEST_USER_COUNT = parseInt(__ENV.TEST_USER_COUNT || '5', 10);
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '';
const REPORT_MONTH = __ENV.REPORT_MONTH || String(new Date().getUTCMonth() + 1);
const REPORT_YEAR = __ENV.REPORT_YEAR || String(new Date().getUTCFullYear());

if (!BASE_URL) {
  throw new Error(
    'Thieu -e BASE_URL=https://<ten-service-render>.onrender.com/api — khong doan URL, phai truyen tay.'
  );
}
if (!TEST_PASSWORD) {
  throw new Error(
    'Thieu -e TEST_PASSWORD=... — mat khau cac tai khoan k6_test_* tao boi create_loadtest_users.'
  );
}

// ===== Metric rieng cho endpoint Dashboard tong hop (endpoint tung OOM) =====
const dashboardOverviewDuration = new Trend('dashboard_overview_duration', true);
const dashboardOverviewErrors = new Rate('dashboard_overview_errors');
const loginErrors = new Rate('login_errors');
const gatewayErrors = new Counter('gateway_5xx_count'); // 502/503/504 = dau hieu OOM/SIGKILL o tang proxy Render

// ===== Kich ban tai: 10 -> 35 -> 50 VU trong ~8 phut (ramp + giu o moi muc) =====
export const options = {
  scenarios: {
    ramping_users: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 10 }, // ramp len 10
        { duration: '2m', target: 10 }, // giu 10 nguoi dong thoi
        { duration: '1m', target: 35 }, // ramp len 35
        { duration: '2m', target: 35 }, // giu 35 nguoi dong thoi
        { duration: '1m', target: 50 }, // ramp len 50
        { duration: '1m', target: 50 }, // giu 50 nguoi dong thoi
      ],
      gracefulRampDown: '15s',
    },
  },
  // Khong abort som — muon thay toan bo duong cong den 50 VU du co vuot nguong hay khong.
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.05', abortOnFail: false }],
    http_req_duration: [{ threshold: 'p(95)<3000', abortOnFail: false }],
    'dashboard_overview_duration': [{ threshold: 'p(95)<5000', abortOnFail: false }],
    'dashboard_overview_errors': [{ threshold: 'rate<0.05', abortOnFail: false }],
    'gateway_5xx_count': [{ threshold: 'count<1', abortOnFail: false }],
  },
};

// Bien module-scope trong k6 la rieng cho tung VU (moi VU chay 1 JS runtime doc lap) nen
// cache token o day an toan, khong bi lo giua cac VU khac nhau.
let authToken = null;

function credentialsForThisVU() {
  const idx = (__VU - 1) % TEST_USER_COUNT;
  return {
    username: `${TEST_USER_PREFIX}${String(idx + 1).padStart(2, '0')}`,
    password: TEST_PASSWORD,
  };
}

function login() {
  const { username, password } = credentialsForThisVU();
  const res = http.post(
    `${BASE_URL}${LOGIN_PATH}`,
    JSON.stringify({ username, password }),
    { headers: { 'Content-Type': 'application/json' }, tags: { endpoint: 'login' } }
  );
  const ok = check(res, {
    'login 200': (r) => r.status === 200,
    'login co access token': (r) => {
      try {
        return !!JSON.parse(r.body).access;
      } catch (e) {
        return false;
      }
    },
  });
  loginErrors.add(!ok);
  if (res.status >= 502 && res.status <= 504) gatewayErrors.add(1);
  if (!ok) return null;
  return JSON.parse(res.body).access;
}

function authHeaders() {
  return { headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' } };
}

export default function () {
  if (!authToken) {
    authToken = login();
    if (!authToken) {
      // Dang nhap loi (vd Render dang OOM/crash-loop) — nghi ngan roi thu lai vong sau,
      // khong ket thuc VU de van con giu nguyen ap luc tai theo dung stages.
      sleep(2);
      return;
    }
  }

  group('me', function () {
    const res = http.get(`${BASE_URL}/auth/me/`, { ...authHeaders(), tags: { endpoint: 'me' } });
    check(res, { 'me 200': (r) => r.status === 200 });
    if (res.status === 401) authToken = null; // token het han/khong hop le -> dang nhap lai vong sau
  });
  sleep(1);

  // Endpoint trong tam: man Dashboard tong hop CEO/GDDT — tung OOM tren Render.
  group('dashboard_overview_ceo', function () {
    const res = http.get(
      `${BASE_URL}/dashboard/overview/?scope=ceo&month=${REPORT_MONTH}&year=${REPORT_YEAR}`,
      { ...authHeaders(), tags: { endpoint: 'dashboard_overview' } }
    );
    dashboardOverviewDuration.add(res.timings.duration);
    const ok = check(res, { 'dashboard overview (ceo) 200': (r) => r.status === 200 });
    dashboardOverviewErrors.add(!ok);
    if (res.status >= 502 && res.status <= 504) gatewayErrors.add(1);
  });
  sleep(1.5);

  group('dashboard_overview_gdt', function () {
    const res = http.get(
      `${BASE_URL}/dashboard/overview/?scope=gdt&month=${REPORT_MONTH}&year=${REPORT_YEAR}`,
      { ...authHeaders(), tags: { endpoint: 'dashboard_overview' } }
    );
    dashboardOverviewDuration.add(res.timings.duration);
    const ok = check(res, { 'dashboard overview (gdt) 200': (r) => r.status === 200 });
    dashboardOverviewErrors.add(!ok);
    if (res.status >= 502 && res.status <= 504) gatewayErrors.add(1);
  });
  sleep(1.5);

  group('kpi_report', function () {
    const res = http.get(
      `${BASE_URL}/kpi/report/?month=${REPORT_MONTH}&year=${REPORT_YEAR}`,
      { ...authHeaders(), tags: { endpoint: 'kpi_report' } }
    );
    check(res, { 'kpi report 200': (r) => r.status === 200 });
    if (res.status >= 502 && res.status <= 504) gatewayErrors.add(1);
  });
  sleep(1);

  group('employees_list', function () {
    const res = http.get(`${BASE_URL}/employees/?page=1`, {
      ...authHeaders(),
      tags: { endpoint: 'employees_list' },
    });
    check(res, { 'employees list 200': (r) => r.status === 200 });
    if (res.status >= 502 && res.status <= 504) gatewayErrors.add(1);
  });
  sleep(2);
}

// ===== Bao cao cuoi cung: p95, ty le loi, dat/khong dat nguong =====
export function handleSummary(data) {
  const m = data.metrics;
  const pct = (rate) => (rate ? (rate.values.rate * 100).toFixed(2) : '0.00');
  const p95 = (metric) => (metric ? metric.values['p(95)'].toFixed(0) : 'N/A');
  const passFail = (name) => {
    const th = m[name] && m[name].thresholds;
    if (!th) return 'N/A';
    const keys = Object.keys(th);
    return keys.every((k) => th[k].ok) ? 'DAT' : 'KHONG DAT';
  };

  const lines = [];
  lines.push('==================== BAO CAO K6 LOAD TEST — v2.1 ====================');
  lines.push(`Muc tieu: ${BASE_URL}  |  Ky bao cao: ${REPORT_MONTH}/${REPORT_YEAR}`);
  lines.push('');
  lines.push('--- Tong quan toan bo request ---');
  lines.push(`  Tong so request           : ${m.http_reqs ? m.http_reqs.values.count : 0}`);
  lines.push(`  p95 latency (tat ca)      : ${p95(m.http_req_duration)} ms  [${passFail('http_req_duration')}]`);
  lines.push(`  Ty le request loi (4xx/5xx/timeout): ${pct(m.http_req_failed)}%  [${passFail('http_req_failed')}]`);
  lines.push('');
  lines.push('--- Endpoint Dashboard tong hop (CEO/GDDT) — endpoint tung OOM ---');
  lines.push(`  p95 latency               : ${p95(m.dashboard_overview_duration)} ms  [${passFail('dashboard_overview_duration')}]`);
  lines.push(`  Ty le loi                 : ${pct(m.dashboard_overview_errors)}%  [${passFail('dashboard_overview_errors')}]`);
  lines.push('');
  lines.push('--- Dau hieu OOM/SIGKILL o tang ha tang (Render tra 502/503/504) ---');
  const gw = m.gateway_5xx_count ? m.gateway_5xx_count.values.count : 0;
  lines.push(`  So request bi 502/503/504 : ${gw}`);
  lines.push(
    gw > 0
      ? '  => CO dau hieu OOM/crash o tang goi. Doi chieu VOI thoi diem nay trong log Render'
      : '  => KHONG thay 502/503/504 trong lan chay nay (van phai doi chieu log Render de chac chan'
  );
  lines.push('     khong co SIGKILL ma request van "treo" cho den khi container restart).');
  lines.push('');
  lines.push('LUU Y: k6 CHI do duoc goc do client (latency/loi HTTP). Muon biet CHINH XAC OOM xay ra');
  lines.push('o muc bao nhieu nguoi dong thoi, phai doi chieu thoi diem cac request cham/loi o tren');
  lines.push('voi log Render (Dashboard service > Logs, loc "Out of memory" / "SIGKILL" / "exit code 137")');
  lines.push('chay SONG SONG trong luc test — xem loadtest/README.md.');
  lines.push('=======================================================================');

  const report = lines.join('\n');
  return {
    stdout: report + '\n\n' + textSummary(data, { indent: ' ', enableColors: true }),
    'loadtest/k6_report.txt': report,
    'loadtest/k6_summary.json': JSON.stringify(data, null, 2),
  };
}
