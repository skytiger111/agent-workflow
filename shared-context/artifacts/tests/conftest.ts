/**
 * tests/conftest.ts — Jest 全域測試設定（ts-jest + Supertest）
 *
 * 測試策略：
 * - 每個 describe block 使用獨立的 Express app instance，確保測試隔離
 * - 使用 nock 攔截 MiniMax API HTTP 呼叫，避免實際網路請求
 * - nock 回復假的 task_id + CDN URL，讓端點正常走到 response 處理邏輯
 *
 * ⚠️ 注意：此檔案需複製至 {project_root}/tests/conftest.ts 才能正常執行
 */

import supertest from 'supertest';
import nock from 'nock';

// 動態匯入 app（避免與 jest.config.js 平行載入時順序問題）
let _app: ReturnType<typeof import('../src/index').createApp> | null = null;

export async function getApp() {
  if (!_app) {
    const { createApp } = await import('../src/index');
    _app = createApp();
  }
  return _app;
}

export function getAgent() {
  return supertest.agent(getApp() as any);
}

/** 產生假的 MiniMax CDN URL */
export function fakeMinimaxUrl(type: 'image' | 'audio' | 'video') {
  const base = 'https://cdn.minimax.io';
  const id = Math.random().toString(36).slice(2, 10);
  if (type === 'image') return `${base}/image/${id}.png`;
  if (type === 'audio') return `${base}/audio/${id}.mp3`;
  return `${base}/video/${id}.mp4`;
}

/**
 * 設定 nock mock：攔截 MiniMax API 並回傳假資料
 * call this once per test to set up the mock before making requests
 */
export function mockMinimaxSuccess(
  endpoint: string,
  overrides: Record<string, unknown> = {},
) {
  // MiniMax API base
  nock('https://api.minimax.io')
    .post(endpoint)
    .reply(200, {
      code: 0,
      msg: 'success',
      data: {
        task_id: `mock_task_${Math.random().toString(36).slice(2, 8)}`,
        ...overrides,
      },
    });
}

/** 清除所有 nock mocks（每個 afterEach 自動呼叫） */
export function clearNockMocks() {
  nock.cleanAll();
}

/** 驗證 API 回應的基本結構（所有成功回應共用） */
export function assertSuccessResponse(
  body: Record<string, unknown>,
  extraFields: string[] = [],
) {
  expect(body).toHaveProperty('success', true);
  expect(body).toHaveProperty('task_id');
  expect(body).toHaveProperty('created_at');
  extraFields.forEach((f) => expect(body).toHaveProperty(f));
}

/** 驗證錯誤回應格式 */
export function assertErrorResponse(body: Record<string, unknown>, statusCode: number) {
  expect(body).toHaveProperty('error');
  expect(typeof body.error).toBe('string');
  expect(body.error!.length).toBeGreaterThan(0);
}
