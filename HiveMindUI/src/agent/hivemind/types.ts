/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

export interface HivemindConfig {
  gatewayUrl: string;
  defaultProvider: string | null;
  timeoutS: number;
  streaming: boolean;
  agent: string | null;
  cacheBypass: boolean;
  systemPrompt: string | null;
}

export const DEFAULT_HIVEMIND_CONFIG: HivemindConfig = {
  gatewayUrl: 'http://localhost:8765',
  defaultProvider: null,
  timeoutS: 300,
  streaming: true,
  agent: null,
  cacheBypass: false,
  systemPrompt: null,
};

export interface AskRequest {
  message: string;
  provider?: string | null;
  model?: string | null;
  timeout_s?: number;
  cache_bypass?: boolean;
  agent?: string | null;
  system_prompt?: string | null;
  files?: string[];
}

export interface AskResponse {
  request_id: string;
  provider: string;
  status: string;
  cached: boolean;
  parallel: boolean;
  agent?: string | null;
  response?: string | null;
  error?: string | null;
  latency_ms?: number | null;
  thinking?: string | null;
  raw_output?: string | null;
}

export interface StreamChunk {
  request_id: string;
  content: string;
  chunk_index: number;
  is_final: boolean;
  tokens_used: number | null;
  provider: string | null;
  metadata: Record<string, unknown> | null;
  thinking?: string | null;
}

export interface StreamSummary {
  cached?: boolean;
  latencyMs?: number | null;
}

export interface HealthResponse {
  status: string;
  [key: string]: unknown;
}

export interface HivemindProviderStatus {
  name: string;
  enabled?: boolean;
  status: string;
  avg_latency_ms?: number | null;
  success_rate?: number | null;
  total_requests?: number;
}

export interface GatewayStatus {
  gateway?: {
    uptime_s?: number;
    total_requests?: number;
    active_requests?: number;
  };
  providers: HivemindProviderStatus[];
}

export const HIVEMIND_PROVIDER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: '🧠 Auto (Smart Route)' },
  { value: 'kimi', label: '🚀 Kimi' },
  { value: 'qwen', label: '🚀 Qwen' },
  { value: 'iflow', label: '⚡ iFlow' },
  { value: 'ollama', label: '⚡ Ollama' },
  { value: 'opencode', label: '⚡ OpenCode' },
  { value: 'obsidian', label: '📚 Obsidian CLI' },
  { value: 'claude', label: '🐢 Claude' },
  { value: 'codex', label: '🐢 Codex' },
  { value: 'gemini', label: '🐢 Gemini' },
  { value: '@fast', label: '⚡ @fast (Kimi+Qwen)' },
  { value: '@all', label: '🌐 @all (All Providers)' },
];

export type CancelRequest = {
  request_id: string;
};

export const PROVIDER_TIERS: Record<string, { emoji: string; label: string; color: string }> = {
  kimi: { emoji: '🚀', label: 'Fast', color: 'arcoblue' },
  qwen: { emoji: '🚀', label: 'Fast', color: 'arcoblue' },
  iflow: { emoji: '⚡', label: 'Balanced', color: 'green' },
  ollama: { emoji: '⚡', label: 'Local', color: 'lime' },
  opencode: { emoji: '⚡', label: 'Balanced', color: 'green' },
  obsidian: { emoji: '📚', label: 'Knowledge', color: 'cyan' },
  claude: { emoji: '🐢', label: 'Deep', color: 'orange' },
  codex: { emoji: '🐢', label: 'Deep', color: 'orange' },
  gemini: { emoji: '🐢', label: 'Deep', color: 'orange' },
  '@fast': { emoji: '⚡', label: 'Group', color: 'purple' },
  '@all': { emoji: '🌐', label: 'Group', color: 'magenta' },
};
