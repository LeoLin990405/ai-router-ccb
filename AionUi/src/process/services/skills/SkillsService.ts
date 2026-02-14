/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type Database from 'better-sqlite3';
import fs from 'fs/promises';
import path from 'path';
import { expandHome, getSkillsRootPath } from './pathUtils';
import type { ISkill } from './types';

const createId = (): string => `skill_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

const parseTags = (value: unknown): string[] => {
  if (!value) {
    return [];
  }

  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }

  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value) as unknown;
      return Array.isArray(parsed) ? parsed.map((item) => String(item)) : [];
    } catch {
      return [];
    }
  }

  return [];
};

export class SkillsService {
  private readonly skillsRootPath: string;

  constructor(
    private readonly db: Database.Database,
    skillsRootPath?: string
  ) {
    this.skillsRootPath = expandHome(skillsRootPath || getSkillsRootPath());
  }

  getRootPath(): string {
    return this.skillsRootPath;
  }

  listSkills(filters?: { category?: string; tags?: string[] }): ISkill[] {
    let query = 'SELECT * FROM skills WHERE 1=1';
    const params: any[] = [];

    if (filters?.category) {
      query += ' AND category = ?';
      params.push(filters.category);
    }

    query += ' ORDER BY updated_at DESC';

    const rows = this.db.prepare(query).all(...params) as any[];
    const skills = rows.map((row) => this.rowToSkill(row));

    if (filters?.tags && filters.tags.length > 0) {
      const required = new Set(filters.tags.map((tag) => String(tag)));
      return skills.filter((skill) => skill.tags.some((tag) => required.has(tag)));
    }

    return skills;
  }

  getSkillById(id: string): ISkill | null {
    const row = this.db.prepare('SELECT * FROM skills WHERE id = ?').get(id) as any;
    return row ? this.rowToSkill(row) : null;
  }

  getSkillByName(name: string, category: string): ISkill | null {
    const row = this.db.prepare('SELECT * FROM skills WHERE name = ? AND category = ?').get(name, category) as any;
    return row ? this.rowToSkill(row) : null;
  }

  async createSkill(params: {
    name: string;
    category: string;
    description?: string;
    content: string;
    manifest?: Record<string, unknown>;
    version?: string;
    author?: string;
    tags?: string[];
  }): Promise<ISkill> {
    const id = createId();
    const now = Date.now();

    const relativeFilePath = path.join(params.category, params.name);
    const fullPath = path.join(this.skillsRootPath, relativeFilePath);

    await fs.mkdir(fullPath, { recursive: true });
    await fs.writeFile(path.join(fullPath, 'SKILL.md'), params.content, 'utf8');

    const manifestText = params.manifest ? JSON.stringify(params.manifest, null, 2) : null;
    if (manifestText) {
      await fs.writeFile(path.join(fullPath, 'manifest.json'), manifestText, 'utf8');
    }

    const stmt = this.db.prepare(`
      INSERT INTO skills (
        id, name, category, description, file_path, content, manifest,
        created_at, updated_at, version, author, tags
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      id,
      params.name,
      params.category,
      params.description || null,
      relativeFilePath,
      params.content,
      manifestText,
      now,
      now,
      params.version || '1.0.0',
      params.author || null,
      JSON.stringify(params.tags || [])
    );

    const created = this.getSkillById(id);
    if (!created) {
      throw new Error('Failed to create skill');
    }

    return created;
  }

  async updateSkill(
    id: string,
    updates: {
      description?: string | null;
      content?: string;
      manifest?: Record<string, unknown> | null;
      version?: string | null;
      author?: string | null;
      tags?: string[];
    }
  ): Promise<ISkill> {
    const skill = this.getSkillById(id);
    if (!skill) {
      throw new Error(`Skill not found: ${id}`);
    }

    const now = Date.now();
    const fullPath = path.join(this.skillsRootPath, skill.file_path);

    const nextContent = updates.content ?? skill.content ?? '';
    const nextManifestText = updates.manifest === undefined ? skill.manifest : updates.manifest ? JSON.stringify(updates.manifest, null, 2) : null;

    if (updates.content !== undefined) {
      await fs.mkdir(fullPath, { recursive: true });
      await fs.writeFile(path.join(fullPath, 'SKILL.md'), nextContent, 'utf8');
    }

    if (updates.manifest !== undefined) {
      await fs.mkdir(fullPath, { recursive: true });
      if (nextManifestText) {
        await fs.writeFile(path.join(fullPath, 'manifest.json'), nextManifestText, 'utf8');
      } else {
        await fs.rm(path.join(fullPath, 'manifest.json'), { force: true });
      }
    }

    const stmt = this.db.prepare(`
      UPDATE skills
      SET description = ?, content = ?, manifest = ?, updated_at = ?, version = ?, author = ?, tags = ?
      WHERE id = ?
    `);

    stmt.run(
      updates.description !== undefined ? updates.description : skill.description,
      nextContent,
      nextManifestText,
      now,
      updates.version !== undefined ? updates.version : skill.version,
      updates.author !== undefined ? updates.author : skill.author,
      JSON.stringify(updates.tags ?? skill.tags ?? []),
      id
    );

    const updated = this.getSkillById(id);
    if (!updated) {
      throw new Error('Failed to update skill');
    }

    return updated;
  }

  async deleteSkill(id: string): Promise<void> {
    const skill = this.getSkillById(id);
    if (!skill) {
      throw new Error(`Skill not found: ${id}`);
    }

    const fullPath = path.join(this.skillsRootPath, skill.file_path);
    await fs.rm(fullPath, { recursive: true, force: true });

    this.db.prepare('DELETE FROM skills WHERE id = ?').run(id);
  }

  async ensureRootDir(): Promise<void> {
    await fs.mkdir(this.skillsRootPath, { recursive: true });
  }

  private rowToSkill(row: any): ISkill {
    return {
      id: row.id,
      name: row.name,
      category: row.category,
      description: row.description ?? null,
      file_path: row.file_path,
      content: row.content ?? null,
      manifest: row.manifest ?? null,
      created_at: row.created_at,
      updated_at: row.updated_at,
      version: row.version ?? null,
      author: row.author ?? null,
      tags: parseTags(row.tags),
    };
  }
}
