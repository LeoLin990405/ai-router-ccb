/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from 'fs/promises';
import path from 'path';
import type { IAITool } from './types';
import { expandHome } from './pathUtils';

export interface IBuiltinToolDefinition {
  id: string;
  name: string;
  type: string;
  display_name: string;
  skills_path: string;
  config_path: string;
  icon_url?: string;
}

export const BUILTIN_TOOLS: IBuiltinToolDefinition[] = [
  {
    id: 'tool-claude',
    name: 'claude-code',
    type: 'builtin',
    display_name: 'Claude Code',
    config_path: '~/.claude/config.json',
    skills_path: '~/.claude/skills/',
  },
  {
    id: 'tool-codex',
    name: 'codex',
    type: 'builtin',
    display_name: 'Codex',
    config_path: '~/.codex/config.json',
    skills_path: '~/.codex/skills/',
  },
  {
    id: 'tool-opencode',
    name: 'opencode',
    type: 'builtin',
    display_name: 'OpenCode',
    config_path: '~/.opencode/config.json',
    skills_path: '~/.opencode/skills/',
  },
];

export class AIToolDetector {
  constructor(private readonly builtinTools: IBuiltinToolDefinition[] = BUILTIN_TOOLS) {}

  async detectAll(): Promise<Array<Pick<IAITool, 'id' | 'name' | 'display_name' | 'skills_path' | 'config_path' | 'detected' | 'enabled' | 'type'>>> {
    const results: Array<Pick<IAITool, 'id' | 'name' | 'display_name' | 'skills_path' | 'config_path' | 'detected' | 'enabled' | 'type'>> = [];

    for (const tool of this.builtinTools) {
      const detected = await this.detectTool(tool.config_path);
      results.push({
        id: tool.id,
        name: tool.name,
        type: tool.type,
        display_name: tool.display_name,
        skills_path: expandHome(tool.skills_path),
        config_path: expandHome(tool.config_path),
        detected: detected ? 1 : 0,
        enabled: 1,
      });
    }

    return results;
  }

  async verifySkillsPathWritable(skillsPath: string): Promise<boolean> {
    try {
      const expanded = expandHome(skillsPath);
      await fs.mkdir(expanded, { recursive: true });
      const probe = path.join(expanded, `.hm_write_probe_${Date.now()}`);
      await fs.writeFile(probe, 'probe', 'utf8');
      await fs.rm(probe, { force: true });
      return true;
    } catch {
      return false;
    }
  }

  private async detectTool(configPath: string): Promise<boolean> {
    try {
      const expandedPath = expandHome(configPath);
      await fs.access(expandedPath);
      return true;
    } catch {
      return false;
    }
  }
}
