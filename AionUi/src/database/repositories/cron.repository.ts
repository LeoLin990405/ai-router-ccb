/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { eq, desc, and, sql } from 'drizzle-orm';
import { BaseRepository } from './base.repository';
import {
  cronJobs,
  cronExecutions,
  type CronJob,
  type NewCronJob,
  type CronExecution,
  type NewCronExecution,
} from '../schema';
import { db } from '../db';

export class CronRepository extends BaseRepository<typeof cronJobs> {
  constructor() {
    super(cronJobs);
  }

  /**
   * Find cron job by name
   */
  async findByName(name: string): Promise<CronJob | null> {
    return this.findOne(eq(cronJobs.name, name));
  }

  /**
   * Find all enabled cron jobs
   */
  async findEnabled(): Promise<CronJob[]> {
    return this.findAll(eq(cronJobs.enabled, true));
  }

  /**
   * Create a new cron job
   */
  async createCronJob(data: NewCronJob): Promise<CronJob> {
    return this.create(data);
  }

  /**
   * Update cron job
   */
  async updateCronJob(
    cronJobId: string,
    data: Partial<
      Pick<CronJob, 'name' | 'schedule' | 'timezone' | 'action' | 'retryOnFailure' | 'enabled'>
    >
  ): Promise<CronJob | null> {
    return this.updateById(cronJobId, data);
  }

  /**
   * Update job status
   */
  async updateStatus(
    cronJobId: string,
    status: 'idle' | 'running' | 'error'
  ): Promise<CronJob | null> {
    return this.updateById(cronJobId, { status });
  }

  /**
   * Update run statistics
   */
  async updateRunStats(
    cronJobId: string,
    success: boolean,
    duration?: number
  ): Promise<CronJob | null> {
    const job = await this.findById(cronJobId);
    if (!job) return null;

    return this.updateById(cronJobId, {
      runCount: sql`${cronJobs.runCount} + 1`,
      successCount: success ? sql`${cronJobs.successCount} + 1` : job.successCount,
      failureCount: !success ? sql`${cronJobs.failureCount} + 1` : job.failureCount,
      lastRunAt: new Date(),
      averageDuration: duration
        ? Math.round(
            ((job.averageDuration || 0) * job.runCount + duration) / (job.runCount + 1)
          )
        : job.averageDuration,
      status: 'idle',
    });
  }

  /**
   * Update next run time
   */
  async updateNextRun(cronJobId: string, nextRunAt: Date): Promise<CronJob | null> {
    return this.updateById(cronJobId, { nextRunAt });
  }

  /**
   * Enable/disable cron job
   */
  async setEnabled(cronJobId: string, enabled: boolean): Promise<CronJob | null> {
    return this.updateById(cronJobId, { enabled });
  }

  // === Cron Execution Operations ===

  /**
   * Create an execution record
   */
  async createExecution(data: NewCronExecution): Promise<CronExecution> {
    const results = await db.insert(cronExecutions).values(data).returning();
    return results[0];
  }

  /**
   * Update execution status
   */
  async updateExecution(
    executionId: string,
    data: Partial<Pick<CronExecution, 'status' | 'output' | 'error' | 'duration' | 'completedAt'>>
  ): Promise<CronExecution | null> {
    const results = await db
      .update(cronExecutions)
      .set(data)
      .where(eq(cronExecutions.id, executionId))
      .returning();
    return results[0] || null;
  }

  /**
   * Find executions for a cron job
   */
  async findExecutions(cronJobId: string, limit = 50, offset = 0): Promise<CronExecution[]> {
    return db
      .select()
      .from(cronExecutions)
      .where(eq(cronExecutions.cronJobId, cronJobId))
      .orderBy(desc(cronExecutions.startedAt))
      .limit(limit)
      .offset(offset);
  }

  /**
   * Find recent failed executions
   */
  async findFailedExecutions(cronJobId: string, limit = 10): Promise<CronExecution[]> {
    return db
      .select()
      .from(cronExecutions)
      .where(and(eq(cronExecutions.cronJobId, cronJobId), eq(cronExecutions.status, 'failed'))!)
      .orderBy(desc(cronExecutions.startedAt))
      .limit(limit);
  }

  /**
   * Get cron job statistics
   */
  async getStats(cronJobId: string) {
    const job = await this.findById(cronJobId);
    if (!job) return null;

    return {
      runCount: job.runCount,
      successCount: job.successCount,
      failureCount: job.failureCount,
      successRate: job.runCount > 0 ? (job.successCount / job.runCount) * 100 : 0,
      averageDuration: job.averageDuration,
      lastRunAt: job.lastRunAt,
      nextRunAt: job.nextRunAt,
      status: job.status,
    };
  }
}
