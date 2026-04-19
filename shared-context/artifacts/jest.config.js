/**
 * Jest 測試設定檔
 *
 * minimax-image-server 使用 Jest 進行測試
 * 測試目標：src/index.ts 的 Express API 端點
 *
 * 執行方式：
 *   cd /Users/tigerclaw/code/minimax-image-server
 *   npm test
 *   npm test -- --coverage  # 含覆蓋率
 */
module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.ts', '**/tests/**/*.test.js'],
  transform: {
    '^.+\\.ts$': ['ts-jest', { tsconfig: 'tsconfig.json' }],
  },
  moduleFileExtensions: ['ts', 'js', 'json'],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov'],
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  testTimeout: 10000,
};
