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

// Skills table
export const skills = pgTable(
  'skills',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: varchar('name', { length: 100 }).notNull().unique(),
    displayName: varchar('display_name', { length: 200 }).notNull(),
    description: text('description'),
    category: varchar('category', { length: 100 }),
    version: varchar('version', { length: 50 }),
    author: varchar('author', { length: 200 }),
    source: text('source'), // URL or local path
    path: text('path').notNull(), // Installation path
    enabled: boolean('enabled').notNull().default(true),
    installed: boolean('installed').notNull().default(true),
    config: jsonb('config'), // Skill configuration
    dependencies: jsonb('dependencies'), // Array of dependency names
    executionCount: integer('execution_count').notNull().default(0),
    lastExecutedAt: timestamp('last_executed_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    nameIdx: index('skills_name_idx').on(table.name),
    categoryIdx: index('skills_category_idx').on(table.category),
    enabledIdx: index('skills_enabled_idx').on(table.enabled),
  })
);

// Skill execution logs table
export const skillLogs = pgTable(
  'skill_logs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    skillId: uuid('skill_id')
      .notNull()
      .references(() => skills.id, { onDelete: 'cascade' }),
    level: varchar('level', { length: 20 }).notNull(), // info, warn, error
    message: text('message').notNull(),
    data: jsonb('data'), // Additional log data
    timestamp: timestamp('timestamp', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    skillIdIdx: index('skill_logs_skill_id_idx').on(table.skillId),
    levelIdx: index('skill_logs_level_idx').on(table.level),
    timestampIdx: index('skill_logs_timestamp_idx').on(table.timestamp),
  })
);

// Zod schemas
export const insertSkillSchema = createInsertSchema(skills);
export const selectSkillSchema = createSelectSchema(skills);

export const insertSkillLogSchema = createInsertSchema(skillLogs);
export const selectSkillLogSchema = createSelectSchema(skillLogs);

// Types
export type Skill = typeof skills.$inferSelect;
export type NewSkill = typeof skills.$inferInsert;
export type SkillLog = typeof skillLogs.$inferSelect;
export type NewSkillLog = typeof skillLogs.$inferInsert;
