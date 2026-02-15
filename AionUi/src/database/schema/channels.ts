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
  boolean,
  integer,
  index,
  jsonb,
} from 'drizzle-orm/pg-core';
import { createInsertSchema, createSelectSchema } from 'drizzle-zod';

// Enums
export const channelTypeEnum = pgEnum('channel_type', ['agent', 'broadcast', 'direct']);
export const messagePriorityEnum = pgEnum('message_priority', ['low', 'normal', 'high', 'urgent']);

// Channels table
export const channels = pgTable(
  'channels',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: varchar('name', { length: 100 }).notNull().unique(),
    displayName: varchar('display_name', { length: 200 }).notNull(),
    description: text('description'),
    type: channelTypeEnum('type').notNull(),
    participants: jsonb('participants').notNull(), // Array of participant objects
    active: boolean('active').notNull().default(true),
    messageCount: integer('message_count').notNull().default(0),
    metadata: jsonb('metadata'),
    lastMessageAt: timestamp('last_message_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    nameIdx: index('channels_name_idx').on(table.name),
    typeIdx: index('channels_type_idx').on(table.type),
    activeIdx: index('channels_active_idx').on(table.active),
  })
);

// Channel messages table
export const channelMessages = pgTable(
  'channel_messages',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    channelId: uuid('channel_id')
      .notNull()
      .references(() => channels.id, { onDelete: 'cascade' }),
    content: text('content').notNull(),
    senderId: uuid('sender_id').notNull(),
    senderName: varchar('sender_name', { length: 200 }).notNull(),
    senderType: varchar('sender_type', { length: 50 }).notNull(), // agent, user, system
    priority: messagePriorityEnum('priority').notNull().default('normal'),
    metadata: jsonb('metadata'),
    status: varchar('status', { length: 20 }).notNull().default('delivered'), // sent, delivered, read
    readBy: jsonb('read_by'), // Array of user/agent IDs
    sentAt: timestamp('sent_at', { withTimezone: true }).notNull().defaultNow(),
    deliveredAt: timestamp('delivered_at', { withTimezone: true }),
  },
  (table) => ({
    channelIdIdx: index('channel_messages_channel_id_idx').on(table.channelId),
    senderIdIdx: index('channel_messages_sender_id_idx').on(table.senderId),
    priorityIdx: index('channel_messages_priority_idx').on(table.priority),
    sentAtIdx: index('channel_messages_sent_at_idx').on(table.sentAt),
  })
);

// Zod schemas
export const insertChannelSchema = createInsertSchema(channels);
export const selectChannelSchema = createSelectSchema(channels);

export const insertChannelMessageSchema = createInsertSchema(channelMessages);
export const selectChannelMessageSchema = createSelectSchema(channelMessages);

// Types
export type Channel = typeof channels.$inferSelect;
export type NewChannel = typeof channels.$inferInsert;
export type ChannelMessage = typeof channelMessages.$inferSelect;
export type NewChannelMessage = typeof channelMessages.$inferInsert;
