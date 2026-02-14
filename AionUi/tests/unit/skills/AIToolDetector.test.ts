import { describe, expect, it } from '@jest/globals';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { AIToolDetector } from '@/process/services/skills/AIToolDetector';

const makeTempDir = async () => {
  return fs.mkdtemp(path.join(os.tmpdir(), 'hm-tools-'));
};

describe('AIToolDetector', () => {
  it('detectAll marks tools as detected when config exists', async () => {
    const temp = await makeTempDir();
    const config = path.join(temp, 'config.json');
    await fs.writeFile(config, '{}', 'utf8');

    const detector = new AIToolDetector([
      {
        id: 'tool-test',
        name: 'test',
        type: 'builtin',
        display_name: 'Test',
        config_path: config,
        skills_path: path.join(temp, 'skills'),
      },
    ]);

    const tools = await detector.detectAll();
    expect(tools[0].detected).toBe(1);

    const writable = await detector.verifySkillsPathWritable(tools[0].skills_path);
    expect(writable).toBe(true);
  });
});
