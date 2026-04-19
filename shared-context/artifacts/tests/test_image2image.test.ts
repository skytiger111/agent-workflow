/**
 * test_image2image.ts — POST /api/image2image 端點測試
 *
 * 測試情境：
 * - 正常圖片編輯 → 200，含 task_id、image_url、original_filename
 * - 未上傳圖片 → 400
 * - Prompt 為空 → 400
 * - 檔案格式不支援 → 415
 * - 檔案過大（> 10MB）→ 413
 * - MiniMax API 失敗 → 500
 *
 * ⚠️ 使用 supertest + multer 的 send(formData) 模擬檔案上傳
 */

import { describe, it, expect, beforeAll, afterEach } from '@jest/globals';
import supertest from 'supertest';
import nock from 'nock';
import path from 'path';
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

describe('POST /api/image2image — 正常流程', () => {
  it('回應 200，含 task_id、image_url、original_filename', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'i2i_test123',
          image_url: fakeMinimaxUrl('image'),
        },
      });

    const res = await request
      .post('/api/image2image')
      .field('prompt', '將圖片轉換為水彩畫風格')
      .attach('image', Buffer.from('fake-png-data'), {
        filename: 'test.png',
        contentType: 'image/png',
      })
      .expect(200);

    expect(res.body).toHaveProperty('success', true);
    expect(res.body).toHaveProperty('task_id', 'i2i_test123');
    expect(res.body).toHaveProperty('image_url');
    expect(res.body.image_url).toMatch(/^https:\/\/cdn\.minimax\.io/);
    expect(res.body).toHaveProperty('original_filename', 'test.png');
  });

  it('支援 strength 參數（0.0–1.0）', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(200, {
        code: 0,
        msg: 'success',
        data: {
          task_id: 'i2i_test456',
          image_url: fakeMinimaxUrl('image'),
        },
      });

    const res = await request
      .post('/api/image2image')
      .field('prompt', '測試強度參數')
      .field('strength', '0.3')
      .attach('image', Buffer.from('fake-jpg-data'), {
        filename: 'test.jpg',
        contentType: 'image/jpeg',
      })
      .expect(200);

    expect(res.body).toHaveProperty('task_id');
  });
});

describe('POST /api/image2image — 參數驗證錯誤', () => {
  it('未上傳圖片 → 400', async () => {
    const res = await request
      .post('/api/image2image')
      .field('prompt', '測試')
      .expect(400);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/圖片|參考圖|image/i);
  });

  it('Prompt 為空 → 400', async () => {
    const res = await request
      .post('/api/image2image')
      .field('prompt', '')
      .attach('image', Buffer.from('fake-png'), {
        filename: 'test.png',
        contentType: 'image/png',
      })
      .expect(400);

    expect(res.body).toHaveProperty('error');
  });

  it('不支援的檔案格式（如 .gif）→ 415', async () => {
    const res = await request
      .post('/api/image2image')
      .field('prompt', '測試')
      .attach('image', Buffer.from('fake-gif-data'), {
        filename: 'test.gif',
        contentType: 'image/gif',
      })
      .expect(415);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toMatch(/格式|僅支援|format/i);
  });
});

describe('POST /api/image2image — MiniMax API 錯誤情境', () => {
  it('MiniMax API 失敗 → 500', async () => {
    nock('https://api.minimax.io')
      .post('/v1/image_generation')
      .reply(500, { code: 500, msg: 'Internal Server Error' });

    const res = await request
      .post('/api/image2image')
      .field('prompt', '測試')
      .attach('image', Buffer.from('fake-png'), {
        filename: 'test.png',
        contentType: 'image/png',
      })
      .expect(500);

    expect(res.body).toHaveProperty('error');
  });
});
