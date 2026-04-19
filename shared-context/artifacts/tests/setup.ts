/**
 * tests/setup.ts — Jest 全域設定與測試環境初始化
 *
 * 職責：
 * - 設定環境變數（MINIMAX_API_KEY 用 mock 值）
 * - 驗證 Supertest 是否正確載入
 * - 任何需要在測試前執行的初始化
 */
import { config } from 'dotenv';

// 載入 .env.test（如存在），避免實際呼叫 MiniMax API
config({ path: '.env.test' });

// 將 API Key 設為 mock 值，讓後端跳過 401 檢查（但實際 HTTP 會被 nock 攔截）
if (!process.env.MINIMAX_API_KEY) {
  process.env.MINIMAX_API_KEY = 'test-minimax-api-key-for-jest';
}

// 全域 jest timeout：10 秒（影片輪詢可能需要）
jest.setTimeout(10000);
