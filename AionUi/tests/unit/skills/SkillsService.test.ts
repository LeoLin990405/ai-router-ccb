import { describe, expect, it } from '@jest/globals';
import BetterSqlite3 from 'better-sqlite3';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { initSchema } from '@/process/database/schema';
import { SkillsService } from '@/process/services/skills/SkillsService';

const makeTempDir = async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'hm-skills-'));
  return root;
};

describe('SkillsService', () => {
  it('creates, lists, updates, deletes skills', async () => {
    const db = new BetterSqlite3(':memory:');
    initSchema(db);

    const skillsRoot = await makeTempDir();
    const service = new SkillsService(db, skillsRoot);

    const created = await service.createSkill({
      name: 'test-skill',
      category: 'custom',
      description: 'hello',
      content: '# Test Skill',
      manifest: { name: 'test-skill', version: '1.0.0' },
      tags: ['a', 'b'],
    });

    expect(created.name).toBe('test-skill');
    expect(created.category).toBe('custom');

    const list = service.listSkills();
    expect(list.length).toBe(1);

    const updated = await service.updateSkill(created.id, {
      content: '# Updated',
      tags: ['b', 'c'],
    });
    expect(updated.content).toContain('Updated');

    const skillDir = path.join(skillsRoot, created.file_path);
    const skillMd = await fs.readFile(path.join(skillDir, 'SKILL.md'), 'utf8');
    expect(skillMd).toContain('Updated');

    await service.deleteSkill(created.id);
    expect(service.listSkills().length).toBe(0);

    await expect(fs.stat(skillDir)).rejects.toBeTruthy();
  });
});
