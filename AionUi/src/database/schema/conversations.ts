/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  pgTable,
  uuid,
  varchar,
  text,
  timestamp,
  pgEnum,
  integer,
  index,
  jsonb,
} from 'drizzle-orm/pg-core';
import { createInsertSchema, createSelectSchema } from 'drizzle-zod';
import { users } from './users';

// Enums
export const conversationPlatformEnum = pgEnum('conversation_platform', [
  'gemini',
  'codex',
  'claude',
  'acp',
  'hivemind',
  'openclaw',
]);

export const messageRoleEnum = pgEnum('message_role', ['user', 'assistant', 'system']);

// Conversations table
export const conversations = pgTable(
  'conversations',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    userId: uuid('user_id')
      .notNull()
      .references(() => users.id, { onDelete: 'cascade' }),
    name: varchar('name', { length: 200 }).notNull(),
    platform: conversationPlatformEnum('platform').notNull(),
    model: varchar('model', { length: 100 }),
    provider: varchar('provider', { length: 100 }),
    workspace: text('workspace'),
    messageCount: integer('message_count').notNull().default(0),
    extra: jsonb('extra'), // Additional metadata
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    userIdIdx: index('conversations_user_id_idx').on(table.userId),
    platformIdx: index('conversations_platform_idx').on(table.platform),
    updatedAtIdx: index('conversations_updated_at_idx').on(table.updatedAt),
  })
);

// Messages table
export const messages = pgTable(
  'messages',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    conversationId: uuid('conversation_id')
      .notNull()
      .references(() => conversations.id, { onDelete: 'cascade' }),
    role: messageRoleEnum('role').notNull(),
    content: text('content').notNull(),
    toolCalls: jsonb('tool_calls'), // Array of tool call objects
    attachments: jsonb('attachments'), // Array of attachment objects
    metadata: jsonb('metadata'), // Additional metadata
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    conversationIdIdx: index('messages_conversation_id_idx').on(table.conversationId),
    createdAtIdx: index('messages_created_at_idx').on(table.createdAt),
    roleIdx: index('messages_role_idx').on(table.role),
  })
);

// Zod schemas
export const insertConversationSchema = createInsertSchema(conversations);
export const selectConversationSchema = createSelectSchema(conversations);

export const insertMessageSchema = createInsertSchema(messages);
export const selectMessageSchema = createSelectSchema(messages);

// Types
export type Conversation = typeof conversations.$inferSelect;
export type NewConversation = typeof conversations.$inferInsert;
export type Message = typeof messages.$inferSelect;
export type NewMessage = typeof messages.$inferInsert;
