/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import '@testing-library/jest-dom';

// Mock Electron IPC
declare global {
  interface Window {
    electron: {
      ipcRenderer: {
        on: jest.Mock;
        send: jest.Mock;
        invoke: jest.Mock;
      };
    };
  }
}

Object.defineProperty(window, 'electron', {
  value: {
    ipcRenderer: {
      on: jest.fn(),
      send: jest.fn(),
      invoke: jest.fn(),
    },
  },
  writable: true,
});

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock ResizeObserver
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
});
