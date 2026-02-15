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
export const teamStatusEnum = pgEnum('team_status', ['idle', 'working', 'paused']);
export const taskStatusEnum = pgEnum('task_status', ['pending', 'in_progress', 'completed', 'failed']);
export const taskPriorityEnum = pgEnum('task_priority', ['low', 'medium', 'high', 'urgent']);

// Teams table
export const teams = pgTable(
  'teams',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: varchar('name', { length: 100 }).notNull().unique(),
    displayName: varchar('display_name', { length: 200 }).notNull(),
    description: text('description'),
    members: jsonb('members').notNull(), // Array of member objects
    workflow: jsonb('workflow'), // { type, coordination }
    status: teamStatusEnum('status').notNull().default('idle'),
    active: boolean('active').notNull().default(true),
    tasksCompleted: integer('tasks_completed').notNull().default(0),
    tasksInProgress: integer('tasks_in_progress').notNull().default(0),
    averageTaskDuration: integer('average_task_duration'), // milliseconds
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    nameIdx: index('teams_name_idx').on(table.name),
    statusIdx: index('teams_status_idx').on(table.status),
    activeIdx: index('teams_active_idx').on(table.active),
  })
);

// Team tasks table
export const teamTasks = pgTable(
  'team_tasks',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    teamId: uuid('team_id')
      .notNull()
      .references(() => teams.id, { onDelete: 'cascade' }),
    title: varchar('title', { length: 200 }).notNull(),
    description: text('description').notNull(),
    priority: taskPriorityEnum('priority').notNull().default('medium'),
    status: taskStatusEnum('status').notNull().default('pending'),
    assignedTo: uuid('assigned_to'), // Member ID
    assignedToName: varchar('assigned_to_name', { length: 200 }),
    input: jsonb('input'), // Task input data
    output: jsonb('output'), // Task output/result
    error: jsonb('error'), // Error details if failed
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    startedAt: timestamp('started_at', { withTimezone: true }),
    completedAt: timestamp('completed_at', { withTimezone: true }),
  },
  (table) => ({
    teamIdIdx: index('team_tasks_team_id_idx').on(table.teamId),
    statusIdx: index('team_tasks_status_idx').on(table.status),
    priorityIdx: index('team_tasks_priority_idx').on(table.priority),
    assignedToIdx: index('team_tasks_assigned_to_idx').on(table.assignedTo),
  })
);

// Zod schemas
export const insertTeamSchema = createInsertSchema(teams);
export const selectTeamSchema = createSelectSchema(teams);

export const insertTeamTaskSchema = createInsertSchema(teamTasks);
export const selectTeamTaskSchema = createSelectSchema(teamTasks);

// Types
export type Team = typeof teams.$inferSelect;
export type NewTeam = typeof teams.$inferInsert;
export type TeamTask = typeof teamTasks.$inferSelect;
export type NewTeamTask = typeof teamTasks.$inferInsert;
