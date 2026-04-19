/**
 * test_health.ts — GET /health、GET /api/history 端點測試
 *
 * 測試情境：
 * - GET /health → 200，含 status、version、uptime_seconds
 * - GET /api/history → 200，含 items（陣列）、total
 * - GET / → 回傳嵌入式 HTML UI（Content-Type: text/html）
 */

import { describe, it, expect, beforeAll } from '@jest/globals';
import supertest from 'supertest';

let app: any;
let request: ReturnType<typeof supertest>;

beforeAll(async () => {
  const { createApp } = await import('../../src/index');
  app = createApp();
  request = supertest(app);
});

describe('GET /health — 健康檢查', () => {
  it('回應 200，含 status、version、uptime_seconds', async () => {
    const res = await request.get('/health').expect(200);

    expect(res.body).toHaveProperty('status', 'ok');
    expect(res.body).toHaveProperty('version');
    expect(typeof res.body.version).toBe('string');
    expect(res.body).toHaveProperty('uptime_seconds');
    expect(typeof res.body.uptime_seconds).toBe('number');
    expect(res.body.uptime_seconds).toBeGreaterThanOrEqual(0);
  });
});

describe('GET /api/history — 生成歷史', () => {
  it('初始應為空列表（items=[]，total=0）', async () => {
    const res = await request.get('/api/history').expect(200);

    expect(res.body).toHaveProperty('items');
    expect(Array.isArray(res.body.items)).toBe(true);
    expect(res.body).toHaveProperty('total', 0);
  });

  it('generate 後 history 包含新項目', async () => {
    // 先建立一筆生成任務
    await request
      .post('/api/generate')
      .send({ prompt: '測試歷史記錄' })
      .expect(200);

    const res = await request.get('/api/history').expect(200);

    expect(res.body).toHaveProperty('total');
    expect(res.body.total).toBeGreaterThan(0);
    expect(Array.isArray(res.body.items)).toBe(true);
    expect(res.body.items.length).toBeGreaterThan(0);

    // 驗證歷史項目的結構
    const first = res.body.items[0];
    expect(first).toHaveProperty('task_id');
    expect(first).toHaveProperty('type');
    expect(first).toHaveProperty('prompt');
    expect(first).toHaveProperty('result_url');
    expect(first).toHaveProperty('created_at');
  });
});

describe('GET / — 嵌入式 HTML UI', () => {
  it('回應 Content-Type: text/html', async () => {
    const res = await request.get('/').expect(200);

    expect(res.headers['content-type']).toMatch(/text\/html/);
    expect(typeof res.text).toBe('string');
    expect(res.text.length).toBeGreaterThan(0);
  });

  it('HTML 包含 Tab 按鈕結構', async () => {
    const res = await request.get('/').expect(200);

    expect(res.text).toMatch(/tab-btn|tab-btn/i);
  });
});
