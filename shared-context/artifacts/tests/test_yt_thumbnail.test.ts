/**
 * test_yt_thumbnail.ts — POST /api/yt-thumbnail 端點測試
 *
 * 測試情境：
 * - 正常 YT 封面生成 → 200，含 task_id、image_url、resolution=1280x720
 * - prompt 為空 → 400
 * - prompt 長度超限（> 2000 字）→ 400
 * - title_text 超過 100 字 → 400
 * - style 為非有效值 → 400（支援 cinematic / vibrant / minimal / dramatic）
 * - title_font_size 超出範圍（< 24 或 > 120）→ 400
 * - 支援所有 style 預設（cinematic / vibrant / minimal / dramatic）
 * - 支援所有 title_position（top_left / top_center / bottom_left / bottom_center）
 * - MiniMax API 失敗 → 500
 * - MiniMax API 業務錯誤 422 → 422
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

// ─── 正常流程測試 ───────────────────────────────────────────────

describe('POST /api/yt-thumbnail — 正常流程', () => {
  it('回應 200，含 task_id、image_url、resolution=1280x720', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'yt_test123',
          image_url: fakeMinimaxUrl('image'),
        },
      });

    const res = await request
      .post('/api/yt-thumbnail')
      .send({
        prompt: '科技產品評測影片封面，暗色背景',
        title_text: 'iPhone 16 評測',
      })
      .expect(200);

    expect(res.body).toHaveProperty('success', true);
    expect(res.body).toHaveProperty('task_id', 'yt_test123');
    expect(res.body).toHaveProperty('image_url');
    expect(res.body.image_url).toMatch(/^https:\/\/cdn\.minimax\.io/);
    expect(res.body).toHaveProperty('resolution', '1280x720');
  });

  it('回應包含 prompt、title_text、created_at', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'yt_test456',
          image_url: fakeMinimaxUrl('image'),
        },
      });

    const res = await request
      .post('/api/yt-thumbnail')
      .send({
        prompt: '遊戲實況封面，明亮色彩',
        title_text: 'Minecraft 生存日記 EP1',
      })
      .expect(200);

    expect(res.body).toHaveProperty('prompt', '遊戲實況封面，明亮色彩');
    expect(res.body).toHaveProperty('title_text', 'Minecraft 生存日記 EP1');
    expect(res.body).toHaveProperty('created_at');
  });

  it('支援自訂標題參數（font_size、color、position）', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'yt_test789',
          image_url: fakeMinimaxUrl('image'),
        },
      });

    const res = await request
      .post('/api/yt-thumbnail')
      .send({
        prompt: '美食影片封面',
        title_text: '手工披薩教學',
        title_font_size: 96,
        title_color: '#FFFF00',
        title_position: 'top_left',
      })
      .expect(200);

    expect(res.body).toHaveProperty('task_id');
  });

  it('無標題文字時也能正常生成（title_text 選填）', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'yt_test_no_title',
          image_url: fakeMinimaxUrl('image'),
        },
      });

    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '純背景縮圖，暗色電影感' })
      .expect(200);

    expect(res.body).toHaveProperty('success', true);
    expect(res.body).toHaveProperty('task_id');
  });
});

// ─── Style 預設支援測試 ─────────────────────────────────────────

describe('POST /api/yt-thumbnail — Style 預設支援', () => {
  const styles = ['cinematic', 'vibrant', 'minimal', 'dramatic'] as const;

  styles.forEach((style) => {
    it(`style="${style}" → 回應 200，含 1280x720`, async () => {
      nock('https://api.minimax.io')
        .post('/v1/image_generation')
        .reply(200, {
          code: 0,
          msg: 'success',
          data: {
            task_id: `yt_style_${style}`,
            image_url: fakeMinimaxUrl('image'),
          },
        });

      const res = await request
        .post('/api/yt-thumbnail')
        .send({ prompt: '測試風格', style })
        .expect(200);

      expect(res.body).toHaveProperty('success', true);
      expect(res.body).toHaveProperty('resolution', '1280x720');
    });
  });
});

// ─── title_position 支援測試 ────────────────────────────────────

describe('POST /api/yt-thumbnail — title_position 支援', () => {
  const positions = [
    'top_left',
    'top_center',
    'bottom_left',
    'bottom_center',
  ] as const;

  positions.forEach((position) => {
    it(`title_position="${position}" → 回應 200`, async () => {
      nock('https://api.minimax.io')
        .post('/v1/image_generation')
        .reply(200, {
          code: 0,
          msg: 'success',
          data: {
            task_id: `yt_pos_${position}`,
            image_url: fakeMinimaxUrl('image'),
          },
        });

      await request
        .post('/api/yt-thumbnail')
        .send({
          prompt: '測試位置',
          title_text: '標題',
          title_position: position,
        })
        .expect(200);
    });
  });
});

// ─── 參數驗證錯誤 ───────────────────────────────────────────────

describe('POST /api/yt-thumbnail — 參數驗證錯誤', () => {
  it('prompt 為空 → 400', async () => {
    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '' })
      .expect(400);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/不能為空|prompt/i);
  });

  it('prompt 未攜帶 → 400', async () => {
    const res = await request
      .post('/api/yt-thumbnail')
      .send({})
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('prompt 長度超限（> 2000 字）→ 400', async () => {
    const longPrompt = '測'.repeat(2001);
    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: longPrompt })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('title_text 超過 100 字 → 400', async () => {
    const longTitle = '標'.repeat(101);
    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試 prompt', title_text: longTitle })
      .expect(400);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/標題|100/i);
  });

  it('style 為非有效值 → 400', async () => {
    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試', style: 'invalid_style' })
      .expect(400);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/style|cinematic|vibrant|minimal|dramatic/i);
  });

  it('title_font_size < 24 → 400', async () => {
    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試', title_text: '標題', title_font_size: 10 })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('title_font_size > 120 → 400', async () => {
    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試', title_text: '標題', title_font_size: 200 })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('title_color 為非十六進位格式 → 400 或接受（取決於實作）', async () => {
    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試', title_text: '標題', title_color: 'not-a-color' });

    // color 驗證為選項行為：可能 400 或忽略（取決於實作嚴格程度）
    expect([200, 400]).toContain(res.status);
  });
});

// ─── MiniMax API 錯誤情境 ───────────────────────────────────────

describe('POST /api/yt-thumbnail — MiniMax API 錯誤情境', () => {
  it('MiniMax API 失敗 → 500', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(500, { code: 500, msg: 'Internal Server Error' });

    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試' })
      .expect(500);

    expect(res.body).toHaveProperty('error');
  });

  it('MiniMax API 回傳業務錯誤 422 → 422', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(422, { code: 422, msg: 'Sensitive content blocked' });

    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試' })
      .expect(422);

    expect(res.body).toHaveProperty('error');
  });

  it('API 頻率限制 429 → 回傳 429', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(429, { code: 429, msg: 'Rate limit exceeded' });

    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試' })
      .expect(429);

    expect(res.body).toHaveProperty('error');
  });

  it('未設定 API Key → 401', async () => {
    const originalKey = process.env.MINIMAX_API_KEY;
    delete process.env.MINIMAX_API_KEY;

    const res = await request
      .post('/api/yt-thumbnail')
      .send({ prompt: '測試' })
      .expect(401);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/API_KEY|未設定/i);

    process.env.MINIMAX_API_KEY = originalKey;
  });
});
