/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * UI State Store - Zustand
 * Manages client-only UI state (sidebar, modals, themes, etc.)
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * UI State Interface
 */
interface UIState {
  // Sidebar
  sidebarCollapsed: boolean;
  sidebarWidth: number;

  // Modals
  activeModal: string | null;
  modalData: Record<string, any>;

  // Loading states
  globalLoading: boolean;
  loadingMessage: string | null;

  // Notifications
  notifications: Notification[];

  // Theme (if not using ThemeContext)
  isDarkMode: boolean;

  // Layout
  layoutMode: 'default' | 'compact' | 'wide';

  // Actions
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSidebarWidth: (width: number) => void;

  openModal: (modalId: string, data?: Record<string, any>) => void;
  closeModal: () => void;

  setGlobalLoading: (loading: boolean, message?: string) => void;

  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;

  toggleTheme: () => void;
  setTheme: (isDark: boolean) => void;

  setLayoutMode: (mode: 'default' | 'compact' | 'wide') => void;
}

/**
 * Notification Interface
 */
interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: number;
  duration?: number;
}

/**
 * UI Store
 */
export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        sidebarCollapsed: false,
        sidebarWidth: 240,
        activeModal: null,
        modalData: {},
        globalLoading: false,
        loadingMessage: null,
        notifications: [],
        isDarkMode: false,
        layoutMode: 'default',

        // Sidebar actions
        toggleSidebar: () =>
          set((state) => ({
            sidebarCollapsed: !state.sidebarCollapsed,
          })),

        setSidebarCollapsed: (collapsed) =>
          set({ sidebarCollapsed: collapsed }),

        setSidebarWidth: (width) =>
          set({ sidebarWidth: width }),

        // Modal actions
        openModal: (modalId, data = {}) =>
          set({
            activeModal: modalId,
            modalData: data,
          }),

        closeModal: () =>
          set({
            activeModal: null,
            modalData: {},
          }),

        // Loading actions
        setGlobalLoading: (loading, message = null) =>
          set({
            globalLoading: loading,
            loadingMessage: message,
          }),

        // Notification actions
        addNotification: (notification) => {
          const id = `notification-${Date.now()}-${Math.random()}`;
          const newNotification: Notification = {
            ...notification,
            id,
            timestamp: Date.now(),
          };

          set((state) => ({
            notifications: [...state.notifications, newNotification],
          }));

          // Auto-remove after duration
          if (notification.duration) {
            setTimeout(() => {
              get().removeNotification(id);
            }, notification.duration);
          }
        },

        removeNotification: (id) =>
          set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
          })),

        clearNotifications: () =>
          set({ notifications: [] }),

        // Theme actions
        toggleTheme: () =>
          set((state) => ({
            isDarkMode: !state.isDarkMode,
          })),

        setTheme: (isDark) =>
          set({ isDarkMode: isDark }),

        // Layout actions
        setLayoutMode: (mode) =>
          set({ layoutMode: mode }),
      }),
      {
        name: 'hivemind-ui-store',
        partialize: (state) => ({
          // Only persist these fields
          sidebarCollapsed: state.sidebarCollapsed,
          sidebarWidth: state.sidebarWidth,
          isDarkMode: state.isDarkMode,
          layoutMode: state.layoutMode,
        }),
      }
    ),
    { name: 'UIStore' }
  )
);

/**
 * Selectors for optimized re-renders
 */
export const uiSelectors = {
  sidebarCollapsed: (state: UIState) => state.sidebarCollapsed,
  sidebarWidth: (state: UIState) => state.sidebarWidth,
  activeModal: (state: UIState) => state.activeModal,
  modalData: (state: UIState) => state.modalData,
  globalLoading: (state: UIState) => state.globalLoading,
  notifications: (state: UIState) => state.notifications,
  isDarkMode: (state: UIState) => state.isDarkMode,
  layoutMode: (state: UIState) => state.layoutMode,
};
