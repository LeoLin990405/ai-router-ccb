module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/src', '<rootDir>/tests'],
  testMatch: ['**/tests/**/*.ts', '**/tests/**/*.tsx', '**/__tests__/**/*.ts', '**/__tests__/**/*.tsx', '**/?(*.)+(spec|test).ts', '**/?(*.)+(spec|test).tsx'],
  transform: {
    '^.+\\.tsx?$': 'ts-jest',
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@process/(.*)$': '<rootDir>/src/process/$1',
    '^@renderer/(.*)$': '<rootDir>/src/renderer/$1',
    '^@worker/(.*)$': '<rootDir>/src/worker/$1',
    '^@mcp/(.*)$': '<rootDir>/src/common/$1',
    '^@mcp/models/(.*)$': '<rootDir>/src/common/models/$1',
    '^@mcp/types/(.*)$': '<rootDir>/src/common/$1',
  },
  collectCoverageFrom: ['src/**/*.ts', 'src/**/*.tsx', '!src/**/*.d.ts', '!src/**/*.test.ts', '!src/**/*.test.tsx', '!src/**/*.spec.ts'],
  setupFilesAfterEnv: ['<rootDir>/tests/jest.setup.ts'],
  testPathIgnorePatterns: ['<rootDir>/tests/jest.setup.ts'],
  testTimeout: 10000,
  verbose: true,
};
