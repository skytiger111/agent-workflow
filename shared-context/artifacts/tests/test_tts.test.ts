/**
 * test_tts.ts — POST /api/tts 端點測試
 *
 * 測試情境：
 * - 正常 TTS 生成 → 200，含 task_id、audio_url、duration_seconds
 * - text 為空 → 400
 * - text 長度超限（> 1000 字）→ 400
 * - 缺少必填欄位 → 400
 * - MiniMax API 失敗（500）
 */

import { describe, it, expect, beforeAll, afterEach } from '@jest/globals';
import supertest from 'supertest';
import nock from 'nock';
import { fakeMinimaxUrl, clearNockMocks } from './conftest';

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

describe('POST /api/tts — 正常流程', () => {
  it('回應 200 且包含 audio_url、duration_seconds', async () => {
    nock('https://api.minimax.io')
      .post('/v1/t2a_v2')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'tts_test123',
          audio_url: fakeMinimaxUrl('audio'),
          duration_seconds: 5.2,
        },
      });

    const res = await request
      .post('/api/tts')
      .send({ text: '歡迎使用 MiniMax 多媒體服務' })
      .expect(200);

    expect(res.body).toHaveProperty('success', true);
    expect(res.body).toHaveProperty('task_id', 'tts_test123');
    expect(res.body).toHaveProperty('audio_url');
    expect(res.body.audio_url).toMatch(/^https:\/\/cdn\.minimax\.io/);
    expect(res.body).toHaveProperty('duration_seconds', 5.2);
  });

  it('支援自訂 voice、speed、pitch 參數', async () => {
    nock('https://api.minimax.io')
      .post('/v1/t2a_v2', (body: any) => {
        return body.voice === 'male_mature';
      })
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'tts_test456',
          audio_url: fakeMinimaxUrl('audio'),
          duration_seconds: 3.0,
        },
      });

    await request
      .post('/api/tts')
      .send({
        text: '測試語音',
        voice: 'male_mature',
        speed: 1.2,
        pitch: 2,
      })
      .expect(200);
  });
});

describe('POST /api/tts — 參數驗證錯誤', () => {
  it('text 為空 → 400', async () => {
    const res = await request
      .post('/api/tts')
      .send({ text: '' })
      .expect(400);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/不能為空|文字/i);
  });

  it('text 未攜帶 → 400', async () => {
    const res = await request
      .post('/api/tts')
      .send({})
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('text 長度超限（> 1000 字）→ 400', async () => {
    const longText = '測'.repeat(1001);
    const res = await request
      .post('/api/tts')
      .send({ text: longText })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });
});

describe('POST /api/tts — MiniMax API 錯誤情境', () => {
  it('MiniMax API 失敗 → 500', async () => {
    nock('https://api.minimax.io')
      .post('/v1/t2a_v2')
      .reply(500, { code: 500, msg: 'Internal Server Error' });

    const res = await request
      .post('/api/tts')
      .send({ text: '測試' })
      .expect(500);

    expect(res.body).toHaveProperty('error');
  });
});
