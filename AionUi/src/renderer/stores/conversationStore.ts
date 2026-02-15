/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Conversation State Store - Zustand
 * Manages client-only conversation state (active conversation, drafts, etc.)
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * Message Draft Interface
 */
interface MessageDraft {
  conversationId: string;
  content: string;
  lastUpdated: number;
}

/**
 * Conversation State Interface
 */
interface ConversationState {
  // Active conversation
  activeConversationId: string | null;

  // Message drafts (persisted)
  drafts: Record<string, MessageDraft>;

  // Typing indicators
  typingUsers: Record<string, string[]>; // conversationId -> userIds[]

  // Temporary UI state
  scrollToBottom: boolean;
  isComposing: boolean;

  // Search
  searchQuery: string;
  searchResults: string[]; // message IDs

  // Selection
  selectedMessageIds: Set<string>;

  // Actions
  setActiveConversation: (conversationId: string | null) => void;

  saveDraft: (conversationId: string, content: string) => void;
  getDraft: (conversationId: string) => string;
  clearDraft: (conversationId: string) => void;

  setTypingUsers: (conversationId: string, userIds: string[]) => void;
  addTypingUser: (conversationId: string, userId: string) => void;
  removeTypingUser: (conversationId: string, userId: string) => void;

  setScrollToBottom: (scroll: boolean) => void;
  setIsComposing: (composing: boolean) => void;

  setSearchQuery: (query: string) => void;
  setSearchResults: (results: string[]) => void;
  clearSearch: () => void;

  toggleMessageSelection: (messageId: string) => void;
  clearSelection: () => void;
  selectAll: (messageIds: string[]) => void;
}

/**
 * Conversation Store
 */
export const useConversationStore = create<ConversationState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        activeConversationId: null,
        drafts: {},
        typingUsers: {},
        scrollToBottom: false,
        isComposing: false,
        searchQuery: '',
        searchResults: [],
        selectedMessageIds: new Set(),

        // Active conversation actions
        setActiveConversation: (conversationId) =>
          set({
            activeConversationId: conversationId,
            scrollToBottom: true,
            selectedMessageIds: new Set(),
          }),

        // Draft actions
        saveDraft: (conversationId, content) =>
          set((state) => ({
            drafts: {
              ...state.drafts,
              [conversationId]: {
                conversationId,
                content,
                lastUpdated: Date.now(),
              },
            },
          })),

        getDraft: (conversationId) => {
          const draft = get().drafts[conversationId];
          return draft?.content || '';
        },

        clearDraft: (conversationId) =>
          set((state) => {
            const { [conversationId]: _, ...rest } = state.drafts;
            return { drafts: rest };
          }),

        // Typing indicators
        setTypingUsers: (conversationId, userIds) =>
          set((state) => ({
            typingUsers: {
              ...state.typingUsers,
              [conversationId]: userIds,
            },
          })),

        addTypingUser: (conversationId, userId) =>
          set((state) => {
            const current = state.typingUsers[conversationId] || [];
            if (current.includes(userId)) {
              return state;
            }
            return {
              typingUsers: {
                ...state.typingUsers,
                [conversationId]: [...current, userId],
              },
            };
          }),

        removeTypingUser: (conversationId, userId) =>
          set((state) => {
            const current = state.typingUsers[conversationId] || [];
            return {
              typingUsers: {
                ...state.typingUsers,
                [conversationId]: current.filter((id) => id !== userId),
              },
            };
          }),

        // UI state actions
        setScrollToBottom: (scroll) =>
          set({ scrollToBottom: scroll }),

        setIsComposing: (composing) =>
          set({ isComposing: composing }),

        // Search actions
        setSearchQuery: (query) =>
          set({ searchQuery: query }),

        setSearchResults: (results) =>
          set({ searchResults: results }),

        clearSearch: () =>
          set({
            searchQuery: '',
            searchResults: [],
          }),

        // Selection actions
        toggleMessageSelection: (messageId) =>
          set((state) => {
            const newSelection = new Set(state.selectedMessageIds);
            if (newSelection.has(messageId)) {
              newSelection.delete(messageId);
            } else {
              newSelection.add(messageId);
            }
            return { selectedMessageIds: newSelection };
          }),

        clearSelection: () =>
          set({ selectedMessageIds: new Set() }),

        selectAll: (messageIds) =>
          set({ selectedMessageIds: new Set(messageIds) }),
      }),
      {
        name: 'hivemind-conversation-store',
        partialize: (state) => ({
          // Only persist drafts
          drafts: state.drafts,
        }),
      }
    ),
    { name: 'ConversationStore' }
  )
);

/**
 * Selectors for optimized re-renders
 */
export const conversationSelectors = {
  activeConversationId: (state: ConversationState) => state.activeConversationId,
  drafts: (state: ConversationState) => state.drafts,
  draft: (conversationId: string) => (state: ConversationState) =>
    state.drafts[conversationId]?.content || '',
  typingUsers: (conversationId: string) => (state: ConversationState) =>
    state.typingUsers[conversationId] || [],
  scrollToBottom: (state: ConversationState) => state.scrollToBottom,
  isComposing: (state: ConversationState) => state.isComposing,
  searchQuery: (state: ConversationState) => state.searchQuery,
  searchResults: (state: ConversationState) => state.searchResults,
  selectedMessageIds: (state: ConversationState) => state.selectedMessageIds,
};
