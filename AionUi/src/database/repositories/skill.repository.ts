/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { eq, desc, and, sql } from 'drizzle-orm';
import { BaseRepository } from './base.repository';
import { skills, skillLogs, type Skill, type NewSkill, type SkillLog, type NewSkillLog } from '../schema';
import { db } from '../db';

export class SkillRepository extends BaseRepository<typeof skills> {
  constructor() {
    super(skills);
  }

  /**
   * Find skill by name
   */
  async findByName(name: string): Promise<Skill | null> {
    return this.findOne(eq(skills.name, name));
  }

  /**
   * Find all enabled skills
   */
  async findEnabled(): Promise<Skill[]> {
    return this.findAll(eq(skills.enabled, true));
  }

  /**
   * Find skills by category
   */
  async findByCategory(category: string): Promise<Skill[]> {
    return this.findAll(eq(skills.category, category));
  }

  /**
   * Create a new skill
   */
  async createSkill(data: NewSkill): Promise<Skill> {
    return this.create(data);
  }

  /**
   * Update skill configuration
   */
  async updateSkill(
    skillId: string,
    data: Partial<Pick<Skill, 'displayName' | 'description' | 'version' | 'config' | 'enabled'>>
  ): Promise<Skill | null> {
    return this.updateById(skillId, data);
  }

  /**
   * Increment execution count
   */
  async incrementExecutionCount(skillId: string): Promise<Skill | null> {
    return this.updateById(skillId, {
      executionCount: sql`${skills.executionCount} + 1`,
      lastExecutedAt: new Date(),
    });
  }

  /**
   * Enable/disable skill
   */
  async setEnabled(skillId: string, enabled: boolean): Promise<Skill | null> {
    return this.updateById(skillId, { enabled });
  }

  // === Skill Log Operations ===

  /**
   * Create a skill execution log
   */
  async createLog(data: NewSkillLog): Promise<SkillLog> {
    const results = await db.insert(skillLogs).values(data).returning();
    return results[0];
  }

  /**
   * Find logs for a skill
   */
  async findLogs(skillId: string, limit = 50, offset = 0): Promise<SkillLog[]> {
    return db
      .select()
      .from(skillLogs)
      .where(eq(skillLogs.skillId, skillId))
      .orderBy(desc(skillLogs.executedAt))
      .limit(limit)
      .offset(offset);
  }

  /**
   * Find logs by status
   */
  async findLogsByStatus(skillId: string, status: string): Promise<SkillLog[]> {
    return db
      .select()
      .from(skillLogs)
      .where(and(eq(skillLogs.skillId, skillId), eq(skillLogs.status, status))!)
      .orderBy(desc(skillLogs.executedAt));
  }

  /**
   * Get skill statistics
   */
  async getStats(skillId: string) {
    const skill = await this.findById(skillId);
    if (!skill) return null;

    const logs = await this.findLogs(skillId, 100);

    const successCount = logs.filter((l) => l.status === 'success').length;
    const failureCount = logs.filter((l) => l.status === 'failed').length;
    const avgDuration = logs.reduce((acc, l) => acc + (l.duration || 0), 0) / logs.length || 0;

    return {
      executionCount: skill.executionCount,
      successCount,
      failureCount,
      successRate: logs.length > 0 ? (successCount / logs.length) * 100 : 0,
      averageDuration: Math.round(avgDuration),
      lastExecutedAt: skill.lastExecutedAt,
    };
  }
}
