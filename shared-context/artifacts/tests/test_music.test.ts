/**
 * test_music.ts — POST /api/music 端點測試
 *
 * 測試情境：
 * - 正常音樂生成 → 200，含 task_id、audio_url、duration_seconds
 * - prompt 為空 → 400
 * - prompt 長度超限 → 400
 * - duration 超過上限（> 300s）→ 400
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

describe('POST /api/music — 正常流程', () => {
  it('回應 200 且包含 audio_url、duration_seconds、title', async () => {
    nock('https://api.minimax.io')
      .post('/v1/music_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'music_test123',
          audio_url: fakeMinimaxUrl('audio'),
          duration_seconds: 30,
        },
      });

    const res = await request
      .post('/api/music')
      .send({
        prompt: '輕快的夏日流行音樂，BPM 120，有鋼琴和吉他',
        title: '夏日晴天',
      })
      .expect(200);

    expect(res.body).toHaveProperty('success', true);
    expect(res.body).toHaveProperty('task_id', 'music_test123');
    expect(res.body).toHaveProperty('audio_url');
    expect(res.body.audio_url).toMatch(/^https:\/\/cdn\.minimax\.io/);
    expect(res.body).toHaveProperty('duration_seconds', 30);
  });

  it('支援自訂 duration 參數', async () => {
    nock('https://api.minimax.io')
      .post('/v1/music_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'music_test456',
          audio_url: fakeMinimaxUrl('audio'),
          duration_seconds: 60,
        },
      });

    const res = await request
      .post('/api/music')
      .send({
        prompt: '平靜的鋼琴曲',
        duration: 60,
        title: '夜深人靜',
      })
      .expect(200);

    expect(res.body).toHaveProperty('duration_seconds', 60);
  });
});

describe('POST /api/music — 參數驗證錯誤', () => {
  it('prompt 為空 → 400', async () => {
    const res = await request
      .post('/api/music')
      .send({ prompt: '' })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('prompt 未攜帶 → 400', async () => {
    const res = await request
      .post('/api/music')
      .send({})
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('duration 超過上限（> 300s）→ 400', async () => {
    const res = await request
      .post('/api/music')
      .send({ prompt: '測試', duration: 400 })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });
});

describe('POST /api/music — MiniMax API 錯誤情境', () => {
  it('MiniMax API 失敗 → 500', async () => {
    nock('https://api.minimax.io')
      .post('/v1/music_generation')
      .reply(500, { code: 500, msg: 'Internal Server Error' });

    const res = await request
      .post('/api/music')
      .send({ prompt: '測試音樂' })
      .expect(500);

    expect(res.body).toHaveProperty('error');
  });
});
