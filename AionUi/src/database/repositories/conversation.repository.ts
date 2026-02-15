/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { eq, and, desc, sql } from 'drizzle-orm';
import { BaseRepository } from './base.repository';
import {
  conversations,
  messages,
  type Conversation,
  type NewConversation,
  type Message,
  type NewMessage,
} from '../schema';
import { db } from '../db';

export class ConversationRepository extends BaseRepository<typeof conversations> {
  constructor() {
    super(conversations);
  }

  /**
   * Find all conversations for a user
   */
  async findByUserId(userId: string, limit = 50, offset = 0): Promise<Conversation[]> {
    return db
      .select()
      .from(conversations)
      .where(eq(conversations.userId, userId))
      .orderBy(desc(conversations.updatedAt))
      .limit(limit)
      .offset(offset);
  }

  /**
   * Find conversation by ID and user ID
   */
  async findByIdAndUserId(conversationId: string, userId: string): Promise<Conversation | null> {
    return this.findOne(
      and(eq(conversations.id, conversationId), eq(conversations.userId, userId))!
    );
  }

  /**
   * Create a new conversation
   */
  async createConversation(data: NewConversation): Promise<Conversation> {
    return this.create(data);
  }

  /**
   * Update conversation metadata
   */
  async updateConversation(
    conversationId: string,
    data: Partial<Pick<Conversation, 'name' | 'model' | 'systemPrompt' | 'metadata'>>
  ): Promise<Conversation | null> {
    return this.updateById(conversationId, {
      ...data,
      updatedAt: new Date(),
    });
  }

  /**
   * Increment message count
   */
  async incrementMessageCount(conversationId: string): Promise<Conversation | null> {
    return this.updateById(conversationId, {
      messageCount: sql`${conversations.messageCount} + 1`,
      updatedAt: new Date(),
    });
  }

  /**
   * Archive conversation
   */
  async archiveConversation(conversationId: string): Promise<Conversation | null> {
    return this.updateById(conversationId, { archived: true });
  }

  /**
   * Unarchive conversation
   */
  async unarchiveConversation(conversationId: string): Promise<Conversation | null> {
    return this.updateById(conversationId, { archived: false });
  }

  /**
   * Delete conversation (also deletes messages via CASCADE)
   */
  async deleteConversation(conversationId: string): Promise<boolean> {
    return this.deleteById(conversationId);
  }

  // === Message Operations ===

  /**
   * Find all messages in a conversation
   */
  async findMessages(
    conversationId: string,
    limit = 100,
    offset = 0
  ): Promise<Message[]> {
    return db
      .select()
      .from(messages)
      .where(eq(messages.conversationId, conversationId))
      .orderBy(messages.createdAt)
      .limit(limit)
      .offset(offset);
  }

  /**
   * Find a single message
   */
  async findMessageById(messageId: string): Promise<Message | null> {
    const results = await db
      .select()
      .from(messages)
      .where(eq(messages.id, messageId))
      .limit(1);
    return results[0] || null;
  }

  /**
   * Create a new message
   */
  async createMessage(data: NewMessage): Promise<Message> {
    const results = await db.insert(messages).values(data).returning();
    return results[0];
  }

  /**
   * Create multiple messages (for bulk operations)
   */
  async createMessages(data: NewMessage[]): Promise<Message[]> {
    return db.insert(messages).values(data).returning();
  }

  /**
   * Update message content
   */
  async updateMessage(
    messageId: string,
    data: Partial<Pick<Message, 'content' | 'metadata'>>
  ): Promise<Message | null> {
    const results = await db
      .update(messages)
      .set(data)
      .where(eq(messages.id, messageId))
      .returning();
    return results[0] || null;
  }

  /**
   * Delete a message
   */
  async deleteMessage(messageId: string): Promise<boolean> {
    const results = await db.delete(messages).where(eq(messages.id, messageId)).returning();
    return results.length > 0;
  }

  /**
   * Get conversation statistics
   */
  async getStats(conversationId: string) {
    const conv = await this.findById(conversationId);
    if (!conv) return null;

    const messageList = await this.findMessages(conversationId);

    return {
      messageCount: conv.messageCount,
      userMessages: messageList.filter((m) => m.role === 'user').length,
      assistantMessages: messageList.filter((m) => m.role === 'assistant').length,
      createdAt: conv.createdAt,
      updatedAt: conv.updatedAt,
    };
  }
}
