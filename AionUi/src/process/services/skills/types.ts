/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

export type SkillCategory = 'claude-code' | 'codex' | 'opencode' | 'custom';

export interface ISkill {
  id: string;
  name: string;
  category: string;
  description: string | null;
  file_path: string;
  content: string | null;
  manifest: string | null;
  created_at: number;
  updated_at: number;
  version: string | null;
  author: string | null;
  tags: string[];
}

export interface IAITool {
  id: string;
  name: string;
  type: string;
  display_name: string;
  skills_path: string;
  config_path: string | null;
  icon_url: string | null;
  enabled: number;
  detected: number;
  last_detected_at: number | null;
  created_at: number;
  updated_at: number;
}

export interface ISkillToolMapping {
  id: string;
  skill_id: string;
  tool_id: string;
  enabled: number;
  synced: number;
  symlink_path: string | null;
  synced_at: number | null;
  sync_error: string | null;
  created_at: number;
  updated_at: number;
}

export interface ISyncResult {
  skill_id: string;
  tool_id: string;
  success: boolean;
  symlink_path?: string;
  error?: string;
}
