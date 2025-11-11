/**
 * k6 Load Testing Script for Circuit.AI
 *
 * Tests:
 * - API authentication
 * - PCB analysis endpoints
 * - BOM generation
 * - Concurrent user scenarios
 *
 * Run: k6 run load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const analysisTime = new Trend('analysis_time');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 200 },  // Spike to 200 users
    { duration: '5m', target: 200 },  // Stay at 200
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests under 2s
    http_req_failed: ['rate<0.05'],    // Less than 5% errors
    errors: ['rate<0.05'],
  },
};

// API configuration
const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test_key_123';

/**
 * Setup function - runs once per VU
 */
export function setup() {
  // Validate API is accessible
  const res = http.get(`${BASE_URL}/health`);
  check(res, {
    'API is accessible': (r) => r.status === 200,
  });

  return { baseUrl: BASE_URL, apiKey: API_KEY };
}

/**
 * Main test scenario
 */
export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.apiKey}`,
  };

  // Test 1: Health check
  let res = http.get(`${data.baseUrl}/health`, { headers });
  check(res, {
    'health check status 200': (r) => r.status === 200,
  });

  sleep(1);

  // Test 2: Get user info
  res = http.get(`${data.baseUrl}/api/v1/user/me`, { headers });
  check(res, {
    'get user status 200': (r) => r.status === 200,
  });

  errorRate.add(res.status !== 200);

  sleep(1);

  // Test 3: List analyses
  res = http.get(`${data.baseUrl}/api/v1/analyses`, { headers });
  check(res, {
    'list analyses status 200': (r) => r.status === 200,
  });

  errorRate.add(res.status !== 200);

  sleep(2);

  // Test 4: Analyze PCB (mock - just measure API response)
  const startTime = Date.now();

  // Simulate file upload
  const formData = {
    file: http.file(generateMockImage(), 'test.jpg', 'image/jpeg'),
    backend: 'yolo',
    enable_ocr: 'false',
  };

  res = http.post(
    `${data.baseUrl}/api/v1/analyze`,
    formData,
    {
      headers: {
        'Authorization': `Bearer ${data.apiKey}`,
      },
      timeout: '60s',
    }
  );

  const analysisTimeMs = Date.now() - startTime;
  analysisTime.add(analysisTimeMs);

  check(res, {
    'analyze PCB status 200 or 400': (r) => [200, 400].includes(r.status),
    'analyze PCB response time < 10s': () => analysisTimeMs < 10000,
  });

  errorRate.add(![200, 400].includes(res.status));

  sleep(3);

  // Test 5: Get analysis by ID (if successful)
  if (res.status === 200) {
    const body = JSON.parse(res.body);
    const analysisId = body.analysis_id;

    res = http.get(
      `${data.baseUrl}/api/v1/analyses/${analysisId}`,
      { headers }
    );

    check(res, {
      'get analysis status 200': (r) => r.status === 200,
    });
  }

  sleep(2);

  // Test 6: Generate BOM
  res = http.post(
    `${data.baseUrl}/api/v1/bom/generate`,
    JSON.stringify({
      components: [
        { type: 'resistor', value: '10k', quantity: 5 },
        { type: 'capacitor', value: '100nF', quantity: 3 },
      ],
    }),
    { headers }
  );

  check(res, {
    'generate BOM status 200': (r) => r.status === 200,
  });

  errorRate.add(res.status !== 200);

  sleep(1);
}

/**
 * Generate mock image data
 */
function generateMockImage() {
  // Return a small dummy image (1x1 pixel PNG)
  return Uint8Array.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
    0x89, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41,
    0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00,
    0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae,
    0x42, 0x60, 0x82,
  ]).buffer;
}

/**
 * Teardown function
 */
export function teardown(data) {
  console.log('Load test complete');
}
