/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type Database from 'better-sqlite3';
import path from 'path';
import { expandHome } from './pathUtils';
import { SymlinkManager } from './SymlinkManager';
import type { IAITool, ISkill, ISyncResult } from './types';

const createId = (): string => `map_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

export class SyncService {
  constructor(
    private readonly db: Database.Database,
    private readonly skillsRootPath: string,
    private readonly symlinkManager: SymlinkManager = new SymlinkManager()
  ) {}

  listTools(): IAITool[] {
    return (this.db.prepare('SELECT * FROM ai_tools ORDER BY name ASC').all() as any[]) as IAITool[];
  }

  listSkills(): ISkill[] {
    return (this.db.prepare('SELECT * FROM skills ORDER BY updated_at DESC').all() as any[]) as ISkill[];
  }

  ensureMapping(skillId: string, toolId: string): void {
    const existing = this.db
      .prepare('SELECT * FROM skill_tool_mapping WHERE skill_id = ? AND tool_id = ?')
      .get(skillId, toolId) as any;

    if (existing) {
      return;
    }

    const now = Date.now();
    this.db
      .prepare(
        `
        INSERT INTO skill_tool_mapping (
          id, skill_id, tool_id, enabled, synced, symlink_path, synced_at, sync_error, created_at, updated_at
        ) VALUES (?, ?, ?, 1, 0, NULL, NULL, NULL, ?, ?)
      `
      )
      .run(createId(), skillId, toolId, now, now);
  }

  setMappingEnabled(skillId: string, toolId: string, enabled: boolean): void {
    this.ensureMapping(skillId, toolId);
    this.db
      .prepare('UPDATE skill_tool_mapping SET enabled = ?, updated_at = ? WHERE skill_id = ? AND tool_id = ?')
      .run(enabled ? 1 : 0, Date.now(), skillId, toolId);
  }

  async executeAll(): Promise<ISyncResult[]> {
    const mappings = this.db
      .prepare(
        `
        SELECT m.*, t.skills_path AS tool_skills_path, t.enabled AS tool_enabled, t.detected AS tool_detected,
               s.file_path AS skill_file_path
        FROM skill_tool_mapping m
        JOIN ai_tools t ON t.id = m.tool_id
        JOIN skills s ON s.id = m.skill_id
        WHERE m.enabled = 1 AND t.enabled = 1
      `
      )
      .all() as any[];

    const results: ISyncResult[] = [];
    for (const row of mappings) {
      if (!row.tool_detected) {
        results.push({
          skill_id: row.skill_id,
          tool_id: row.tool_id,
          success: false,
          error: 'Tool not detected',
        });
        continue;
      }

      results.push(await this.executeOne(row.skill_id, row.tool_id));
    }

    return results;
  }

  async executeOne(skillId: string, toolId: string): Promise<ISyncResult> {
    const row = this.db
      .prepare(
        `
        SELECT m.*, t.skills_path AS tool_skills_path, t.enabled AS tool_enabled, t.detected AS tool_detected,
               s.file_path AS skill_file_path
        FROM skill_tool_mapping m
        JOIN ai_tools t ON t.id = m.tool_id
        JOIN skills s ON s.id = m.skill_id
        WHERE m.skill_id = ? AND m.tool_id = ?
      `
      )
      .get(skillId, toolId) as any;

    if (!row) {
      this.ensureMapping(skillId, toolId);
      return this.executeOne(skillId, toolId);
    }

    if (!row.enabled || !row.tool_enabled) {
      return { skill_id: skillId, tool_id: toolId, success: false, error: 'Mapping or tool disabled' };
    }

    if (!row.tool_detected) {
      return { skill_id: skillId, tool_id: toolId, success: false, error: 'Tool not detected' };
    }

    const now = Date.now();
    const sourcePath = path.join(this.skillsRootPath, row.skill_file_path);
    const toolSkillsPath = expandHome(row.tool_skills_path);
    const targetPath = path.join(toolSkillsPath, row.skill_file_path);

    try {
      await this.symlinkManager.createSymlink(sourcePath, targetPath);
      this.db
        .prepare(
          `
          UPDATE skill_tool_mapping
          SET synced = 1, symlink_path = ?, synced_at = ?, sync_error = NULL, updated_at = ?
          WHERE skill_id = ? AND tool_id = ?
        `
        )
        .run(targetPath, now, now, skillId, toolId);

      return { skill_id: skillId, tool_id: toolId, success: true, symlink_path: targetPath };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.db
        .prepare(
          `
          UPDATE skill_tool_mapping
          SET synced = 0, sync_error = ?, updated_at = ?
          WHERE skill_id = ? AND tool_id = ?
        `
        )
        .run(message, now, skillId, toolId);

      return { skill_id: skillId, tool_id: toolId, success: false, error: message };
    }
  }

  async unsync(skillId: string, toolId: string): Promise<void> {
    const row = this.db
      .prepare(
        `
        SELECT m.symlink_path
        FROM skill_tool_mapping m
        WHERE m.skill_id = ? AND m.tool_id = ?
      `
      )
      .get(skillId, toolId) as { symlink_path?: string } | undefined;

    const targetPath = row?.symlink_path;
    if (targetPath) {
      await this.symlinkManager.removeSymlink(targetPath);
    }

    this.db
      .prepare('UPDATE skill_tool_mapping SET synced = 0, symlink_path = NULL, sync_error = NULL, updated_at = ? WHERE skill_id = ? AND tool_id = ?')
      .run(Date.now(), skillId, toolId);
  }

  status(): { totalSkills: number; syncedSkills: number; errors: number } {
    const totalSkills = (this.db.prepare('SELECT COUNT(*) as cnt FROM skills').get() as any).cnt as number;
    const syncedSkills = (this.db.prepare('SELECT COUNT(*) as cnt FROM skill_tool_mapping WHERE synced = 1').get() as any).cnt as number;
    const errors = (this.db.prepare("SELECT COUNT(*) as cnt FROM skill_tool_mapping WHERE sync_error IS NOT NULL AND sync_error != ''").get() as any).cnt as number;

    return {
      totalSkills,
      syncedSkills,
      errors,
    };
  }
}
