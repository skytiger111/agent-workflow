/**
 * test_video.ts — POST /api/video、GET /api/video/:task_id 端點測試
 *
 * 測試情境：
 * - 正常影片生成（文字模式）→ 200，含 task_id、video_url
 * - 正常影片生成（圖片模式）→ 200，含 task_id、video_url
 * - prompt 與 image_url 皆未攜帶 → 400
 * - duration 超過上限（> 30s）→ 400
 * - GET /api/video/:task_id → 200，含 status、video_url
 * - GET /api/video/:task_id（任務不存在）→ 404
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

// ─── POST /api/video — 正常流程 ────────────────────────────────

describe('POST /api/video — 正常流程', () => {
  it('文字模式：回應 200 且包含 video_url', async () => {
    nock('https://api.minimax.io')
      .post('/v1/video_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'vid_test123',
          video_url: fakeMinimaxUrl('video'),
          status: 'completed',
        },
      });

    const res = await request
      .post('/api/video')
      .send({ prompt: '一隻可愛的貓在沙發上打哈欠' })
      .expect(200);

    expect(res.body).toHaveProperty('success', true);
    expect(res.body).toHaveProperty('task_id', 'vid_test123');
    expect(res.body).toHaveProperty('video_url');
    expect(res.body.video_url).toMatch(/^https:\/\/cdn\.minimax\.io/);
  });

  it('圖片模式：回應 200 且使用 image_url', async () => {
    nock('https://api.minimax.io')
      .post('/v1/video_generation', (body: any) => {
        return body.input && body.input.image_url !== undefined;
      })
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'vid_test456',
          video_url: fakeMinimaxUrl('video'),
          status: 'completed',
        },
      });

    const res = await request
      .post('/api/video')
      .send({
        image_url: 'https://example.com/cat.png',
        prompt: '貓緩慢地眨眼睛',
      })
      .expect(200);

    expect(res.body).toHaveProperty('video_url');
  });

  it('支援自訂 duration 與 resolution', async () => {
    nock('https://api.minimax.io')
      .post('/v1/video_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'vid_test789',
          video_url: fakeMinimaxUrl('video'),
          status: 'completed',
        },
      });

    const res = await request
      .post('/api/video')
      .send({
        prompt: '測試影片',
        duration: 10,
        resolution: '1080p',
      })
      .expect(200);

    expect(res.body).toHaveProperty('task_id');
  });
});

// ─── POST /api/video — 參數驗證錯誤 ────────────────────────────

describe('POST /api/video — 參數驗證錯誤', () => {
  it('prompt 與 image_url 皆未攜帶 → 400', async () => {
    const res = await request
      .post('/api/video')
      .send({})
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('duration 超過上限（> 30s）→ 400', async () => {
    const res = await request
      .post('/api/video')
      .send({ prompt: '測試', duration: 60 })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });
});

// ─── GET /api/video/:task_id — 進度查詢 ──────────────────────

describe('GET /api/video/:task_id — 進度查詢', () => {
  it('任務已完成：回應 200，含 status=completed、video_url', async () => {
    nock('https://api.minimax.io')
      .post('/v1/video_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'vid_query123',
          video_url: fakeMinimaxUrl('video'),
          status: 'completed',
        },
      });

    // 先建立任務（POST）
    const postRes = await request
      .post('/api/video')
      .send({ prompt: '測試' })
      .expect(200);

    const taskId = postRes.body.task_id;

    // 再查詢進度（GET）
    const getRes = await request
      .get(`/api/video/${taskId}`)
      .expect(200);

    expect(getRes.body).toHaveProperty('task_id', taskId);
    expect(getRes.body).toHaveProperty('status', 'completed');
    expect(getRes.body).toHaveProperty('video_url');
    expect(getRes.body).toHaveProperty('progress_percent', 100);
  });

  it('任務不存在 → 404', async () => {
    const res = await request
      .get('/api/video/nonexistent_task_id')
      .expect(404);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/找不到|不存在/i);
  });
});

// ─── POST /api/video — MiniMax API 錯誤情境 ─────────────────

describe('POST /api/video — MiniMax API 錯誤情境', () => {
  it('MiniMax API 失敗 → 500', async () => {
    nock('https://api.minimax.io')
      .post('/v1/video_generation')
      .reply(500, { code: 500, msg: 'Internal Server Error' });

    const res = await request
      .post('/api/video')
      .send({ prompt: '測試' })
      .expect(500);

    expect(res.body).toHaveProperty('error');
  });
});
