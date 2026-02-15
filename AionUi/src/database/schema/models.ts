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
export const providerTypeEnum = pgEnum('provider_type', ['openai', 'anthropic', 'google', 'custom']);

// Providers table
export const providers = pgTable(
  'providers',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: varchar('name', { length: 100 }).notNull(),
    type: providerTypeEnum('type').notNull(),
    apiKey: text('api_key'), // Encrypted
    baseUrl: text('base_url'),
    enabled: boolean('enabled').notNull().default(true),
    config: jsonb('config'), // Additional configuration
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    nameIdx: index('providers_name_idx').on(table.name),
    typeIdx: index('providers_type_idx').on(table.type),
    enabledIdx: index('providers_enabled_idx').on(table.enabled),
  })
);

// Models table
export const models = pgTable(
  'models',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: varchar('name', { length: 100 }).notNull(),
    displayName: varchar('display_name', { length: 200 }).notNull(),
    providerId: uuid('provider_id')
      .notNull()
      .references(() => providers.id, { onDelete: 'cascade' }),
    modelId: varchar('model_id', { length: 100 }).notNull(), // External model ID
    capabilities: jsonb('capabilities').notNull(), // { chat, vision, functionCalling, streaming }
    contextWindow: integer('context_window'),
    maxOutputTokens: integer('max_output_tokens'),
    enabled: boolean('enabled').notNull().default(true),
    metadata: jsonb('metadata'), // Additional metadata
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    providerIdIdx: index('models_provider_id_idx').on(table.providerId),
    nameIdx: index('models_name_idx').on(table.name),
    enabledIdx: index('models_enabled_idx').on(table.enabled),
  })
);

// Zod schemas
export const insertProviderSchema = createInsertSchema(providers);
export const selectProviderSchema = createSelectSchema(providers);

export const insertModelSchema = createInsertSchema(models);
export const selectModelSchema = createSelectSchema(models);

// Types
export type Provider = typeof providers.$inferSelect;
export type NewProvider = typeof providers.$inferInsert;
export type Model = typeof models.$inferSelect;
export type NewModel = typeof models.$inferInsert;
