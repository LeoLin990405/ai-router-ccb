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
  boolean,
  integer,
  index,
  jsonb,
} from 'drizzle-orm/pg-core';
import { createInsertSchema, createSelectSchema } from 'drizzle-zod';

// MCP servers table
export const mcpServers = pgTable(
  'mcp_servers',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: varchar('name', { length: 100 }).notNull().unique(),
    displayName: varchar('display_name', { length: 200 }).notNull(),
    description: text('description'),
    command: varchar('command', { length: 255 }).notNull(),
    args: jsonb('args'), // Array of command arguments
    env: jsonb('env'), // Environment variables (sensitive data masked)
    enabled: boolean('enabled').notNull().default(true),
    status: varchar('status', { length: 20 }).notNull().default('disconnected'), // connected, disconnected, error
    capabilities: jsonb('capabilities'), // { tools, resources, prompts }
    toolCount: integer('tool_count').notNull().default(0),
    resourceCount: integer('resource_count').notNull().default(0),
    lastConnected: timestamp('last_connected', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    nameIdx: index('mcp_servers_name_idx').on(table.name),
    enabledIdx: index('mcp_servers_enabled_idx').on(table.enabled),
    statusIdx: index('mcp_servers_status_idx').on(table.status),
  })
);

// Zod schemas
export const insertMcpServerSchema = createInsertSchema(mcpServers);
export const selectMcpServerSchema = createSelectSchema(mcpServers);

// Types
export type McpServer = typeof mcpServers.$inferSelect;
export type NewMcpServer = typeof mcpServers.$inferInsert;
