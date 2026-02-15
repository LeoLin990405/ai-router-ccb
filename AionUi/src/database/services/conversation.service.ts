/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Conversation service - handles conversation and message management
 */

import { ConversationRepository } from '../repositories';
import type { Conversation, NewConversation, Message, NewMessage } from '../schema';

export class ConversationService {
  private conversationRepo: ConversationRepository;

  constructor() {
    this.conversationRepo = new ConversationRepository();
  }

  /**
   * Get all conversations for a user
   */
  async getUserConversations(
    userId: string,
    options: { limit?: number; offset?: number } = {}
  ): Promise<Conversation[]> {
    const { limit = 50, offset = 0 } = options;
    return this.conversationRepo.findByUserId(userId, limit, offset);
  }

  /**
   * Get a conversation by ID (with ownership check)
   */
  async getConversation(conversationId: string, userId: string): Promise<Conversation | null> {
    return this.conversationRepo.findByIdAndUserId(conversationId, userId);
  }

  /**
   * Create a new conversation
   */
  async createConversation(data: {
    userId: string;
    name: string;
    platform: 'hivemind' | 'gemini' | 'claude' | 'codex' | 'custom';
    model: string;
    systemPrompt?: string;
    metadata?: any;
  }): Promise<Conversation> {
    const newConversation: NewConversation = {
      userId: data.userId,
      name: data.name,
      platform: data.platform,
      model: data.model,
      systemPrompt: data.systemPrompt,
      metadata: data.metadata,
      messageCount: 0,
      archived: false,
    };

    return this.conversationRepo.createConversation(newConversation);
  }

  /**
   * Update conversation metadata
   */
  async updateConversation(
    conversationId: string,
    userId: string,
    data: {
      name?: string;
      model?: string;
      systemPrompt?: string;
      metadata?: any;
    }
  ): Promise<Conversation | null> {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    return this.conversationRepo.updateConversation(conversationId, data);
  }

  /**
   * Archive a conversation
   */
  async archiveConversation(conversationId: string, userId: string): Promise<Conversation | null> {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    return this.conversationRepo.archiveConversation(conversationId);
  }

  /**
   * Unarchive a conversation
   */
  async unarchiveConversation(
    conversationId: string,
    userId: string
  ): Promise<Conversation | null> {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    return this.conversationRepo.unarchiveConversation(conversationId);
  }

  /**
   * Delete a conversation
   */
  async deleteConversation(conversationId: string, userId: string): Promise<boolean> {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    return this.conversationRepo.deleteConversation(conversationId);
  }

  // === Message Operations ===

  /**
   * Get messages for a conversation
   */
  async getMessages(
    conversationId: string,
    userId: string,
    options: { limit?: number; offset?: number } = {}
  ): Promise<Message[]> {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    const { limit = 100, offset = 0 } = options;
    return this.conversationRepo.findMessages(conversationId, limit, offset);
  }

  /**
   * Add a message to a conversation
   */
  async addMessage(
    conversationId: string,
    userId: string,
    data: {
      role: 'user' | 'assistant' | 'system' | 'tool';
      content: string;
      toolCalls?: any;
      toolCallId?: string;
      attachments?: any;
      metadata?: any;
    }
  ): Promise<Message> {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    const newMessage: NewMessage = {
      conversationId,
      role: data.role,
      content: data.content,
      toolCalls: data.toolCalls,
      toolCallId: data.toolCallId,
      attachments: data.attachments,
      metadata: data.metadata,
    };

    // Create message
    const message = await this.conversationRepo.createMessage(newMessage);

    // Increment conversation message count
    await this.conversationRepo.incrementMessageCount(conversationId);

    return message;
  }

  /**
   * Add multiple messages (bulk operation)
   */
  async addMessages(
    conversationId: string,
    userId: string,
    messages: Array<{
      role: 'user' | 'assistant' | 'system' | 'tool';
      content: string;
      toolCalls?: any;
      toolCallId?: string;
      attachments?: any;
      metadata?: any;
    }>
  ): Promise<Message[]> {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    const newMessages: NewMessage[] = messages.map((msg) => ({
      conversationId,
      role: msg.role,
      content: msg.content,
      toolCalls: msg.toolCalls,
      toolCallId: msg.toolCallId,
      attachments: msg.attachments,
      metadata: msg.metadata,
    }));

    // Create messages
    const createdMessages = await this.conversationRepo.createMessages(newMessages);

    // Update conversation message count
    for (let i = 0; i < messages.length; i++) {
      await this.conversationRepo.incrementMessageCount(conversationId);
    }

    return createdMessages;
  }

  /**
   * Update a message
   */
  async updateMessage(
    messageId: string,
    userId: string,
    data: {
      content?: string;
      metadata?: any;
    }
  ): Promise<Message | null> {
    // Get message and verify ownership through conversation
    const message = await this.conversationRepo.findMessageById(messageId);
    if (!message) {
      throw new Error('Message not found');
    }

    const conversation = await this.conversationRepo.findByIdAndUserId(
      message.conversationId,
      userId
    );
    if (!conversation) {
      throw new Error('Access denied');
    }

    return this.conversationRepo.updateMessage(messageId, data);
  }

  /**
   * Delete a message
   */
  async deleteMessage(messageId: string, userId: string): Promise<boolean> {
    // Get message and verify ownership through conversation
    const message = await this.conversationRepo.findMessageById(messageId);
    if (!message) {
      throw new Error('Message not found');
    }

    const conversation = await this.conversationRepo.findByIdAndUserId(
      message.conversationId,
      userId
    );
    if (!conversation) {
      throw new Error('Access denied');
    }

    return this.conversationRepo.deleteMessage(messageId);
  }

  /**
   * Get conversation statistics
   */
  async getConversationStats(conversationId: string, userId: string) {
    // Verify ownership
    const conversation = await this.conversationRepo.findByIdAndUserId(conversationId, userId);
    if (!conversation) {
      throw new Error('Conversation not found or access denied');
    }

    return this.conversationRepo.getStats(conversationId);
  }
}
