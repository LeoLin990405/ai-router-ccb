import { describe, expect, it } from '@jest/globals';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { SymlinkManager } from '@/process/services/skills/SymlinkManager';

const makeTempDir = async () => {
  return fs.mkdtemp(path.join(os.tmpdir(), 'hm-symlink-'));
};

describe('SymlinkManager', () => {
  it('creates and removes symlink', async () => {
    const temp = await makeTempDir();
    const source = path.join(temp, 'source');
    const target = path.join(temp, 'target');

    await fs.mkdir(source, { recursive: true });
    await fs.writeFile(path.join(source, 'SKILL.md'), 'hello', 'utf8');

    const manager = new SymlinkManager();
    await manager.createSymlink(source, target);

    expect(await manager.isSymlink(target)).toBe(true);

    const content = await fs.readFile(path.join(target, 'SKILL.md'), 'utf8');
    expect(content).toBe('hello');

    await manager.removeSymlink(target);
    expect(await manager.isSymlink(target)).toBe(false);
  });
});
