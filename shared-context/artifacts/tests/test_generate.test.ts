/**
 * test_generate.ts — POST /api/generate 端點測試
 *
 * 測試情境：
 * - 正常生成（文字 Prompt）→ 200，含 task_id、image_url
 * - prompt 為空 → 400
 * - prompt 長度超限（> 2000 字）→ 400
 * - 缺少必填欄位 → 400
 * - 無 API Key（401）
 * - MiniMax API 失敗（500）
 */

import { describe, it, expect, beforeAll, afterEach } from '@jest/globals';
import supertest from 'supertest';
import nock from 'nock';
import { fakeMinimaxUrl, clearNockMocks } from './conftest';

// Supertest 延遲匯入（配合 ts-jest）
let app: any;
let request: ReturnType<typeof supertest>;

beforeAll(async () => {
  const { createApp } = await import('../../src/index');
  app = createApp();
  request = supertest(app);
});

afterEach(() => {
  clearNockMocks();
});

// ─── 正常流程測試 ───────────────────────────────────────────────

describe('POST /api/generate — 正常流程', () => {
  it('回應 200 且包含 success、task_id、image_url', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'img_test123',
          image_url: fakeMinimaxUrl('image'),
        },
      });

    const res = await request
      .post('/api/generate')
      .send({ prompt: '一隻在森林中奔跑的可愛老虎' })
      .expect(200);

    expect(res.body).toHaveProperty('success', true);
    expect(res.body).toHaveProperty('task_id', 'img_test123');
    expect(res.body).toHaveProperty('image_url');
    expect(res.body.image_url).toMatch(/^https:\/\/cdn\.minimax\.io/);
  });

  it('回應包含 prompt 與 created_at', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: { task_id: 'img_test456', image_url: fakeMinimaxUrl('image') },
      });

    const res = await request
      .post('/api/generate')
      .send({ prompt: '測試 prompt' })
      .expect(200);

    expect(res.body).toHaveProperty('prompt', '測試 prompt');
    expect(res.body).toHaveProperty('created_at');
  });

  it('支援自訂 aspect_ratio 與 resolution', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation', (body: any) => {
        // 驗證 aspect_ratio 有傳入 request body
        return body.aspect_ratio === '16:9';
      })
      .reply(200, {
        code: 0,
        msg: 'success',
        data: { task_id: 'img_test789', image_url: fakeMinimaxUrl('image') },
      });

    await request
      .post('/api/generate')
      .send({ prompt: '測試', aspect_ratio: '16:9', resolution: '512x512' })
      .expect(200);
  });
});

// ─── 參數驗證錯誤 ───────────────────────────────────────────────

describe('POST /api/generate — 參數驗證錯誤', () => {
  it('prompt 為空 → 400', async () => {
    const res = await request
      .post('/api/generate')
      .send({ prompt: '' })
      .expect(400);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/不能為空|prompt/i);
  });

  it('prompt 未攜帶 → 400', async () => {
    const res = await request
      .post('/api/generate')
      .send({})
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('prompt 長度超限（> 2000 字）→ 400', async () => {
    const longPrompt = '好'.repeat(2001);
    const res = await request
      .post('/api/generate')
      .send({ prompt: longPrompt })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });
});

// ─── MiniMax API 錯誤情境 ───────────────────────────────────────

describe('POST /api/generate — MiniMax API 錯誤情境', () => {
  it('未設定 API Key → 401', async () => {
    // 移除環境變數，讓後端走到 401 分支
    const originalKey = process.env.MINIMAX_API_KEY;
    delete process.env.MINIMAX_API_KEY;

    const res = await request
      .post('/api/generate')
      .send({ prompt: '測試' })
      .expect(401);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/API_KEY|未設定/i);

    process.env.MINIMAX_API_KEY = originalKey;
  });

  it('MiniMax API 回傳錯誤 → 500', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(500, { code: 500, msg: 'Internal Server Error' });

    const res = await request
      .post('/api/generate')
      .send({ prompt: '測試' })
      .expect(500);

    expect(res.body).toHaveProperty('error');
  });

  it('MiniMax API 回傳業務錯誤 422 → 回傳 422', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(422, { code: 422, msg: 'Sensitive content blocked' });

    const res = await request
      .post('/api/generate')
      .send({ prompt: '測試' })
      .expect(422);

    expect(res.body).toHaveProperty('error');
  });

  it('API 頻率限制 429 → 回傳 429', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(429, { code: 429, msg: 'Rate limit exceeded' });

    const res = await request
      .post('/api/generate')
      .send({ prompt: '測試' })
      .expect(429);

    expect(res.body).toHaveProperty('error');
  });
});
