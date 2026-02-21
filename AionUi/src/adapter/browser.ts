/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { bridge, logger } from '@office-ai/platform';
import type { ElectronBridgeAPI } from '@/types/electron';
import { io, type Socket } from 'socket.io-client';

interface CustomWindow extends Window {
  electronAPI?: ElectronBridgeAPI;
  __bridgeEmitter?: { emit: (name: string, data: unknown) => void };
  __emitBridgeCallback?: (name: string, data: unknown) => void;
  __websocketReconnect?: () => void;
}

const win = window as CustomWindow;

/**
 * 适配electron的API到浏览器中,建立renderer和main的通信桥梁, 与preload.ts中的注入对应
 * */
if (win.electronAPI) {
  // Electron 环境 - 使用 IPC 通信
  bridge.adapter({
    emit(name, data) {
      return win.electronAPI.emit(name, data);
    },
    on(emitter) {
      win.electronAPI?.on((event) => {
        try {
          const { value } = event;
          const { name, data } = JSON.parse(value);
          emitter.emit(name, data);
        } catch (e) {
          console.warn('JSON parsing error:', e);
        }
      });
    },
  });
} else {
  // Web 环境 - 使用 Socket.IO 客户端通信（与服务端 SocketIOManager 匹配）
  // Web runtime bridge: use Socket.IO client to match server-side Socket.IO transport
  type QueuedMessage = { name: string; data: unknown };

  let socket: Socket | null = null;
  let emitterRef: { emit: (name: string, data: unknown) => void } | null = null;
  let reconnectTimer: number | null = null;
  let reconnectDelay = 500;
  let shouldReconnect = true;

  const messageQueue: QueuedMessage[] = [];

  // 1.发送队列中积压的消息
  const flushQueue = () => {
    if (!socket || !socket.connected) return;

    while (messageQueue.length > 0) {
      const queued = messageQueue.shift();
      if (queued) {
        socket.emit(queued.name, queued.data);
      }
    }
  };

  // 2.指数退避重连
  const scheduleReconnect = () => {
    if (reconnectTimer !== null || !shouldReconnect) return;

    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      reconnectDelay = Math.min(reconnectDelay * 2, 8000);
      connect();
    }, reconnectDelay);
  };

  // 3.建立 Socket.IO 连接
  const connect = () => {
    if (socket?.connected) return;

    // 断开旧连接（如果存在）
    if (socket) {
      socket.removeAllListeners();
      socket.disconnect();
      socket = null;
    }

    const baseURL = `${window.location.protocol}//${window.location.host || `${window.location.hostname}:25808`}`;

    try {
      socket = io(baseURL, {
        // Prefer cookie-based session auth in browser mode.
        auth: {},
        withCredentials: true, // 发送 httpOnly cookie（hivemind-session）用于认证
        // Keep polling-only in WebUI for stable connectivity across environments.
        transports: ['polling'],
        upgrade: false,
        reconnection: false, // 手动控制重连
      });
    } catch (error) {
      scheduleReconnect();
      return;
    }

    socket.on('connect', () => {
      reconnectDelay = 500;
      flushQueue();
    });

    // 使用 onAny 接收所有服务端事件并转发到 bridge emitter
    // Use onAny to receive all server events and forward to bridge emitter
    socket.onAny((eventName: string, ...args: unknown[]) => {
      if (!emitterRef) return;

      const data = args[0];

      // 处理认证过期
      if (eventName === 'auth-expired') {
        console.warn('[Socket.IO] Authentication expired, stopping reconnection');
        shouldReconnect = false;

        if (reconnectTimer !== null) {
          window.clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }

        socket?.disconnect();

        setTimeout(() => {
          window.location.href = '/login';
        }, 1000);
        return;
      }

      emitterRef.emit(eventName, data);
    });

    socket.on('disconnect', () => {
      scheduleReconnect();
    });

    socket.on('connect_error', () => {
      scheduleReconnect();
    });
  };

  // 4.确保连接已建立
  const ensureSocket = () => {
    if (!socket || socket.disconnected) {
      connect();
    }
  };

  bridge.adapter({
    emit(name, data) {
      const message: QueuedMessage = { name, data };

      ensureSocket();

      if (socket && socket.connected) {
        try {
          socket.emit(name, data);
          return;
        } catch (error) {
          scheduleReconnect();
        }
      }

      messageQueue.push(message);
    },
    on(emitter) {
      emitterRef = emitter;
      win.__bridgeEmitter = emitter;

      win.__emitBridgeCallback = (name: string, data: unknown) => {
        emitter.emit(name, data);
      };

      ensureSocket();
    },
  });

  connect();

  // Expose reconnection control for login flow
  win.__websocketReconnect = () => {
    shouldReconnect = true;
    reconnectDelay = 500;
    connect();
  };
}

logger.provider({
  log(log) {
    console.log('process.log', log.type, ...log.logs);
  },
  path() {
    return Promise.resolve('');
  },
});
