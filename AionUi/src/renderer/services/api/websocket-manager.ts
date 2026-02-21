/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * WebSocket Manager for Real-time Communication
 */

import { io, type Socket } from 'socket.io-client';
import type { EventCallback, UnsubscribeFn, WebSocketOptions, TokenStorage } from './types';
import { ConnectionStatus } from './types';
import { tokenStorage as defaultTokenStorage } from './token-storage';

/**
 * WebSocket connection manager using Socket.IO
 */
export class WebSocketManager {
  private socket: Socket | null = null;
  private tokenStorage: TokenStorage;
  private baseURL: string;
  private options: Required<WebSocketOptions>;
  private status: ConnectionStatus = ConnectionStatus.DISCONNECTED;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private eventListeners = new Map<string, Set<EventCallback>>();
  private statusListeners = new Set<(status: ConnectionStatus) => void>();

  constructor(baseURL: string = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:25808', tokenStorage: TokenStorage = defaultTokenStorage, options: WebSocketOptions = {}) {
    this.baseURL = baseURL;
    this.tokenStorage = tokenStorage;
    this.options = {
      autoReconnect: options.autoReconnect ?? true,
      reconnectDelay: options.reconnectDelay ?? 1000,
      maxReconnectAttempts: options.maxReconnectAttempts ?? 10,
      token: options.token ?? undefined,
    };
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.socket?.connected) {
      console.warn('WebSocket already connected');
      return;
    }

    this.updateStatus(ConnectionStatus.CONNECTING);

    const token = this.options.token;

    this.socket = io(this.baseURL, {
      auth: token ? { token } : {},
      // Browser mode keeps polling-only for stability.
      // Some environments can intermittently fail websocket upgrade and spam warnings.
      transports: ['polling'],
      upgrade: false,
      reconnection: false, // We handle reconnection manually
    });

    this.setupEventHandlers();
  }

  /**
   * Setup Socket.IO event handlers
   */
  private setupEventHandlers(): void {
    if (!this.socket) return;

    // Connection events
    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.updateStatus(ConnectionStatus.CONNECTED);
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.updateStatus(ConnectionStatus.DISCONNECTED);

      // Auto reconnect if enabled
      if (this.options.autoReconnect && reason === 'io server disconnect') {
        this.reconnect();
      }
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      this.updateStatus(ConnectionStatus.ERROR);

      if (this.options.autoReconnect) {
        this.reconnect();
      }
    });

    // Auth expired event - disconnect and notify
    this.socket.on('auth-expired', (data) => {
      console.warn('Authentication expired:', data.message);
      this.updateStatus(ConnectionStatus.ERROR);
      this.disconnect();

      // Notify listeners about auth expiration
      const listeners = this.eventListeners.get('auth-expired');
      if (listeners) {
        listeners.forEach((callback) => callback(data));
      }
    });

    // Ping/Pong for heartbeat
    this.socket.on('ping', (data) => {
      // Respond with pong
      this.socket?.emit('pong', { timestamp: Date.now() });
    });

    // Forward all custom events to registered listeners
    this.socket.onAny((eventName, ...args) => {
      // Skip internal Socket.IO events
      if (eventName === 'connect' || eventName === 'disconnect' || eventName === 'connect_error') {
        return;
      }

      const listeners = this.eventListeners.get(eventName);
      if (listeners) {
        const data = args[0]; // Assume first arg is the data
        listeners.forEach((callback) => {
          try {
            callback(data);
          } catch (error) {
            console.error(`Error in event listener for "${eventName}":`, error);
          }
        });
      }
    });
  }

  /**
   * Reconnect with exponential backoff
   */
  private reconnect(): void {
    if (this.reconnectTimer) {
      return; // Already attempting to reconnect
    }

    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      this.updateStatus(ConnectionStatus.ERROR);
      return;
    }

    this.reconnectAttempts++;
    this.updateStatus(ConnectionStatus.RECONNECTING);

    const delay = Math.min(
      this.options.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000 // Max 30 seconds
    );

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /**
   * Subscribe to an event
   */
  subscribe<T = any>(event: string, callback: EventCallback<T>): UnsubscribeFn {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }

    this.eventListeners.get(event)!.add(callback);

    // Return unsubscribe function
    return () => {
      const listeners = this.eventListeners.get(event);
      if (listeners) {
        listeners.delete(callback);
        if (listeners.size === 0) {
          this.eventListeners.delete(event);
        }
      }
    };
  }

  /**
   * Emit an event to server
   */
  emit(event: string, data?: any): void {
    if (!this.socket?.connected) {
      console.warn('Cannot emit event: WebSocket not connected');
      return;
    }

    this.socket.emit(event, data);
  }

  /**
   * Subscribe to connection status changes
   */
  onStatusChange(callback: (status: ConnectionStatus) => void): UnsubscribeFn {
    this.statusListeners.add(callback);
    return () => {
      this.statusListeners.delete(callback);
    };
  }

  /**
   * Update connection status and notify listeners
   */
  private updateStatus(status: ConnectionStatus): void {
    this.status = status;
    this.statusListeners.forEach((callback) => {
      try {
        callback(status);
      } catch (error) {
        console.error('Error in status change listener:', error);
      }
    });
  }

  /**
   * Get current connection status
   */
  getStatus(): ConnectionStatus {
    return this.status;
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }

    this.eventListeners.clear();
    this.statusListeners.clear();
    this.updateStatus(ConnectionStatus.DISCONNECTED);
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.status === ConnectionStatus.CONNECTED;
  }
}

// Singleton instance
let wsManagerInstance: WebSocketManager | null = null;

/**
 * Get the WebSocket manager singleton
 */
export function getWebSocketManager(): WebSocketManager {
  if (!wsManagerInstance) {
    wsManagerInstance = new WebSocketManager();
  }
  return wsManagerInstance;
}
