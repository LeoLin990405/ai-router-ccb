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
export const cronActionTypeEnum = pgEnum('cron_action_type', ['command', 'skill', 'http']);
export const cronStatusEnum = pgEnum('cron_status', ['idle', 'running', 'paused', 'error']);

// Cron jobs table
export const cronJobs = pgTable(
  'cron_jobs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: varchar('name', { length: 100 }).notNull().unique(),
    displayName: varchar('display_name', { length: 200 }).notNull(),
    description: text('description'),
    schedule: varchar('schedule', { length: 100 }).notNull(), // Cron expression
    timezone: varchar('timezone', { length: 100 }).notNull().default('UTC'),
    enabled: boolean('enabled').notNull().default(true),
    status: cronStatusEnum('status').notNull().default('idle'),
    action: jsonb('action').notNull(), // { type, command/skillId/url, ... }
    retryOnFailure: boolean('retry_on_failure').notNull().default(false),
    maxRetries: integer('max_retries').notNull().default(0),
    lastRun: timestamp('last_run', { withTimezone: true }),
    nextRun: timestamp('next_run', { withTimezone: true }),
    runCount: integer('run_count').notNull().default(0),
    successCount: integer('success_count').notNull().default(0),
    failureCount: integer('failure_count').notNull().default(0),
    averageExecutionTime: integer('average_execution_time'), // milliseconds
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    nameIdx: index('cron_jobs_name_idx').on(table.name),
    enabledIdx: index('cron_jobs_enabled_idx').on(table.enabled),
    statusIdx: index('cron_jobs_status_idx').on(table.status),
    nextRunIdx: index('cron_jobs_next_run_idx').on(table.nextRun),
  })
);

// Cron execution history table
export const cronExecutions = pgTable(
  'cron_executions',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    jobId: uuid('job_id')
      .notNull()
      .references(() => cronJobs.id, { onDelete: 'cascade' }),
    status: varchar('status', { length: 20 }).notNull(), // success, failure, running
    startedAt: timestamp('started_at', { withTimezone: true }).notNull(),
    completedAt: timestamp('completed_at', { withTimezone: true }),
    duration: integer('duration'), // milliseconds
    output: jsonb('output'), // Execution output
    error: jsonb('error'), // Error details if failed
  },
  (table) => ({
    jobIdIdx: index('cron_executions_job_id_idx').on(table.jobId),
    statusIdx: index('cron_executions_status_idx').on(table.status),
    startedAtIdx: index('cron_executions_started_at_idx').on(table.startedAt),
  })
);

// Zod schemas
export const insertCronJobSchema = createInsertSchema(cronJobs);
export const selectCronJobSchema = createSelectSchema(cronJobs);

export const insertCronExecutionSchema = createInsertSchema(cronExecutions);
export const selectCronExecutionSchema = createSelectSchema(cronExecutions);

// Types
export type CronJob = typeof cronJobs.$inferSelect;
export type NewCronJob = typeof cronJobs.$inferInsert;
export type CronExecution = typeof cronExecutions.$inferSelect;
export type NewCronExecution = typeof cronExecutions.$inferInsert;
