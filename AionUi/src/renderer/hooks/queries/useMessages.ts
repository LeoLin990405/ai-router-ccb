/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Messages React Query Hooks with Optimistic Updates
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/renderer/config/queryClient';
import { api } from '@/renderer/services/api';
import type { Message } from './useConversations';

/**
 * Create message request
 */
export interface CreateMessageRequest {
  conversationId: string;
  content: string;
  role?: 'user' | 'assistant' | 'system';
  metadata?: Record<string, any>;
}

/**
 * Update message request
 */
export interface UpdateMessageRequest {
  content?: string;
  metadata?: Record<string, any>;
}

/**
 * Create message
 */
async function createMessage(data: CreateMessageRequest): Promise<Message> {
  const response = await api.call<{ success: boolean; data: Message }>('messages.create', data);

  if (!response.success || !response.data) {
    throw new Error('Failed to create message');
  }

  return response.data;
}

/**
 * Update message
 */
async function updateMessage(id: string, data: UpdateMessageRequest): Promise<Message> {
  const response = await api.call<{ success: boolean; data: Message }>('messages.update', {
    id,
    ...data,
  });

  if (!response.success || !response.data) {
    throw new Error('Failed to update message');
  }

  return response.data;
}

/**
 * Delete message
 */
async function deleteMessage(id: string): Promise<void> {
  const response = await api.call<{ success: boolean }>('messages.delete', { id });

  if (!response.success) {
    throw new Error('Failed to delete message');
  }
}

/**
 * Hook: Create message (with optimistic update)
 */
export function useCreateMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMessage,
    // Optimistic update
    onMutate: async (newMessage) => {
      const { conversationId } = newMessage;

      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: queryKeys.conversations.messages(conversationId),
      });

      // Snapshot previous messages
      const previousMessages = queryClient.getQueryData<Message[]>(
        queryKeys.conversations.messages(conversationId)
      );

      // Create optimistic message
      const optimisticMessage: Message = {
        id: `temp-${Date.now()}`,
        conversationId,
        role: newMessage.role || 'user',
        content: newMessage.content,
        metadata: newMessage.metadata,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      // Optimistically update
      queryClient.setQueryData<Message[]>(
        queryKeys.conversations.messages(conversationId),
        (old) => [...(old || []), optimisticMessage]
      );

      // Return context with previous value
      return { previousMessages, conversationId };
    },
    // On success, replace temp message with real one
    onSuccess: (newMessage, variables, context) => {
      if (!context) return;

      const { conversationId } = context;

      // Replace optimistic message with real one
      queryClient.setQueryData<Message[]>(
        queryKeys.conversations.messages(conversationId),
        (old) => {
          if (!old) return [newMessage];
          return old.map((msg) =>
            msg.id.startsWith('temp-') ? newMessage : msg
          );
        }
      );

      // Invalidate conversation (update lastMessageAt)
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversations.detail(conversationId),
      });
    },
    // On error, roll back
    onError: (err, variables, context) => {
      if (!context) return;

      const { previousMessages, conversationId } = context;

      if (previousMessages) {
        queryClient.setQueryData(
          queryKeys.conversations.messages(conversationId),
          previousMessages
        );
      }
    },
  });
}

/**
 * Hook: Update message (with optimistic update)
 */
export function useUpdateMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateMessageRequest }) =>
      updateMessage(id, data),
    // Optimistic update
    onMutate: async ({ id, data }) => {
      // Find which conversation this message belongs to
      // Note: This requires knowing the conversationId, which we can pass in the mutation
      const allConversations = queryClient.getQueriesData<Message[]>({
        queryKey: queryKeys.conversations.all(),
      });

      let conversationId: string | null = null;
      let previousMessage: Message | undefined;

      // Find the conversation and message
      for (const [queryKey, messages] of allConversations) {
        if (!messages) continue;
        const message = messages.find((msg) => msg.id === id);
        if (message) {
          conversationId = message.conversationId;
          previousMessage = message;
          break;
        }
      }

      if (!conversationId || !previousMessage) {
        return { previousMessage: null, conversationId: null };
      }

      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: queryKeys.conversations.messages(conversationId),
      });

      // Optimistically update
      queryClient.setQueryData<Message[]>(
        queryKeys.conversations.messages(conversationId),
        (old) => {
          if (!old) return old;
          return old.map((msg) =>
            msg.id === id
              ? { ...msg, ...data, updatedAt: new Date().toISOString() }
              : msg
          );
        }
      );

      return { previousMessage, conversationId };
    },
    // On error, roll back
    onError: (err, { id }, context) => {
      if (!context?.previousMessage || !context.conversationId) return;

      queryClient.setQueryData<Message[]>(
        queryKeys.conversations.messages(context.conversationId),
        (old) => {
          if (!old) return old;
          return old.map((msg) => (msg.id === id ? context.previousMessage! : msg));
        }
      );
    },
    // Always refetch
    onSettled: (_, __, { id }, context) => {
      if (context?.conversationId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.conversations.messages(context.conversationId),
        });
      }
    },
  });
}

/**
 * Hook: Delete message (with optimistic update)
 */
export function useDeleteMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, conversationId }: { id: string; conversationId: string }) =>
      deleteMessage(id),
    // Optimistic update
    onMutate: async ({ id, conversationId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: queryKeys.conversations.messages(conversationId),
      });

      // Snapshot previous messages
      const previousMessages = queryClient.getQueryData<Message[]>(
        queryKeys.conversations.messages(conversationId)
      );

      // Optimistically remove
      queryClient.setQueryData<Message[]>(
        queryKeys.conversations.messages(conversationId),
        (old) => (old || []).filter((msg) => msg.id !== id)
      );

      return { previousMessages, conversationId };
    },
    // On error, roll back
    onError: (err, { conversationId }, context) => {
      if (!context?.previousMessages) return;

      queryClient.setQueryData(
        queryKeys.conversations.messages(conversationId),
        context.previousMessages
      );
    },
    // Always refetch
    onSettled: (_, __, { conversationId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversations.messages(conversationId),
      });
    },
  });
}
