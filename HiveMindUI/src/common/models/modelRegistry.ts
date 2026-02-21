/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * HiveMind 模型注册表
 * Model Registry for HiveMind system
 *
 * 集中管理所有 Provider 的可用模型配置
 * Centrally manages all available models for each provider
 */

import type { ProviderModels, ModelConfig } from '@/types/acpTypes';

/**
 * Codex (OpenAI) 模型配置
 */
const codexModels: ModelConfig[] = [
  {
    id: 'gpt-5.2-codex',
    displayName: 'GPT-5.2 Codex',
    description: 'Frontier agentic coding model',
    isDefault: true,
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 60,
    isPaid: true,
    speedTier: 'medium',
  },
  {
    id: 'gpt-5.1-codex-max',
    displayName: 'GPT-5.1 Codex Max',
    description: 'Deep and fast reasoning',
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 90,
    isPaid: true,
    speedTier: 'slow',
  },
  {
    id: 'gpt-5.2',
    displayName: 'GPT-5.2',
    description: 'Latest frontier model',
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 60,
    isPaid: true,
    speedTier: 'medium',
  },
  {
    id: 'gpt-5.1-codex-mini',
    displayName: 'GPT-5.1 Codex Mini',
    description: 'Cheaper, faster, less capable',
    capabilities: ['code'],
    estimatedResponseTime: 30,
    isPaid: true,
    speedTier: 'fast',
  },
];

/**
 * Gemini 模型配置
 */
const geminiModels: ModelConfig[] = [
  {
    id: 'gemini-2.5-flash',
    displayName: 'Gemini 2.5 Flash',
    description: 'Gemini 2.5 快速版',
    isDefault: true,
    capabilities: ['code', 'frontend', 'reasoning'],
    estimatedResponseTime: 60,
    isPaid: false,
    speedTier: 'medium',
  },
  {
    id: 'gemini-2.5-pro',
    displayName: 'Gemini 2.5 Pro',
    description: 'Gemini 2.5 专业版',
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 120,
    isPaid: false,
    speedTier: 'slow',
  },
  {
    id: 'gemini-2.0-flash',
    displayName: 'Gemini 2.0 Flash',
    description: 'Gemini 2.0 快速版',
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 45,
    isPaid: false,
    speedTier: 'fast',
  },
];

/**
 * Kimi 模型配置
 */
const kimiModels: ModelConfig[] = [
  {
    id: 'kimi-normal',
    displayName: 'Kimi - 标准模式',
    description: '标准对话模式，快速响应',
    isDefault: true,
    capabilities: ['chinese', 'code', 'long-context'],
    estimatedResponseTime: 10,
    isPaid: false,
    speedTier: 'fast',
  },
  {
    id: 'kimi-thinking',
    displayName: 'Kimi - 思考模式',
    description: '启用思考链，提供详细推理过程',
    capabilities: ['chinese', 'reasoning', 'long-context'],
    estimatedResponseTime: 25,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Qwen 模型配置
 * 注意：模型名称需要与 Qwen CLI 的 settings.json 中的配置一致
 */
const qwenModels: ModelConfig[] = [
  {
    id: 'qwen3-coder-plus',
    displayName: 'Qwen3 Coder Plus',
    description: '代码专用模型，Python/SQL 能力强',
    isDefault: true,
    capabilities: ['code', 'chinese', 'data'],
    estimatedResponseTime: 12,
    isPaid: true,
    speedTier: 'fast',
  },
  {
    id: 'qwen3-max-2026-01-23',
    displayName: 'Qwen3 Max (思考模式)',
    description: '最强模型，启用思考链',
    capabilities: ['code', 'chinese', 'reasoning'],
    estimatedResponseTime: 30,
    isPaid: true,
    speedTier: 'medium',
  },
];

/**
 * iFlow 模型配置
 */
const iflowModels: ModelConfig[] = [
  {
    id: 'iflow-normal',
    displayName: 'iFlow - 标准模式',
    description: '工作流自动化标准模式',
    isDefault: true,
    capabilities: ['workflow', 'chinese'],
    estimatedResponseTime: 30,
    isPaid: false,
    speedTier: 'medium',
  },
  {
    id: 'iflow-thinking',
    displayName: 'iFlow - 思考模式',
    description: '启用思考链的工作流模式',
    capabilities: ['workflow', 'reasoning', 'chinese'],
    estimatedResponseTime: 60,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * OpenCode 模型配置
 */
const opencodeModels: ModelConfig[] = [
  {
    id: 'minimax-cn-coding-plan/MiniMax-M2.5',
    displayName: 'MiniMax M2.5 - 付费',
    description: 'MiniMax 付费模型，能力更强',
    isDefault: true,
    capabilities: ['code', 'chinese'],
    estimatedResponseTime: 30,
    isPaid: true,
    speedTier: 'medium',
  },
  {
    id: 'opencode/minimax-m2.5-free',
    displayName: 'MiniMax M2.5 - 免费',
    description: 'MiniMax 免费模型',
    capabilities: ['code', 'chinese'],
    estimatedResponseTime: 45,
    isPaid: false,
    speedTier: 'medium',
  },
  {
    id: 'opencode/kimi-k2.5-free',
    displayName: 'Kimi K2.5 - 免费',
    description: 'Kimi 免费模型',
    capabilities: ['code', 'chinese'],
    estimatedResponseTime: 50,
    isPaid: false,
    speedTier: 'medium',
  },
  {
    id: 'opencode/glm-4.7-free',
    displayName: 'GLM-4.7 - 免费',
    description: '智谱 GLM-4.7 免费模型',
    capabilities: ['code', 'chinese'],
    estimatedResponseTime: 45,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Ollama 模型配置（回退列表）
 * 注意：优先从本地 Ollama 服务动态获取模型
 */
const ollamaModels: ModelConfig[] = [
  {
    id: 'qwen2.5:7b',
    displayName: 'Qwen 2.5 7B',
    description: 'Qwen 2.5 7B 模型（推荐，代码能力强）',
    isDefault: true,
    capabilities: ['local', 'code', 'chinese'],
    estimatedResponseTime: 40,
    isPaid: false,
    speedTier: 'medium',
  },
  {
    id: 'llama3.2:3b',
    displayName: 'Llama 3.2 3B',
    description: 'Llama 3.2 3B 轻量模型',
    capabilities: ['local', 'code'],
    estimatedResponseTime: 30,
    isPaid: false,
    speedTier: 'fast',
  },
  {
    id: 'codellama:7b',
    displayName: 'Code Llama 7B',
    description: 'Code Llama 7B 代码专用模型',
    capabilities: ['local', 'code'],
    estimatedResponseTime: 45,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Goose 模型配置
 */
const gooseModels: ModelConfig[] = [
  {
    id: 'goose-default',
    displayName: 'Goose - 默认',
    description: 'Goose CLI 默认模型',
    isDefault: true,
    capabilities: ['code'],
    estimatedResponseTime: 40,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Auggie 模型配置
 */
const auggieModels: ModelConfig[] = [
  {
    id: 'auggie-default',
    displayName: 'Auggie - 默认',
    description: 'Auggie CLI 默认模型',
    isDefault: true,
    capabilities: ['code'],
    estimatedResponseTime: 45,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Copilot 模型配置
 */
const copilotModels: ModelConfig[] = [
  {
    id: 'copilot-default',
    displayName: 'Copilot - 默认',
    description: 'GitHub Copilot CLI 默认模型',
    isDefault: true,
    capabilities: ['code'],
    estimatedResponseTime: 35,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * OpenClaw Gateway 模型配置
 */
const openclawModels: ModelConfig[] = [
  {
    id: 'openclaw-default',
    displayName: 'OpenClaw - 默认',
    description: 'OpenClaw Gateway 默认模型',
    isDefault: true,
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 40,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Custom Agent 模型配置
 */
const customModels: ModelConfig[] = [
  {
    id: 'custom-default',
    displayName: 'Custom - 默认',
    description: '自定义 Agent 默认模型',
    isDefault: true,
    capabilities: ['code'],
    estimatedResponseTime: 40,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Qoder 模型配置
 */
const qoderModels: ModelConfig[] = [
  {
    id: 'qoder-default',
    displayName: 'Qoder - 默认',
    description: 'Qoder 代码助手默认模型',
    isDefault: true,
    capabilities: ['code'],
    estimatedResponseTime: 40,
    isPaid: false,
    speedTier: 'medium',
  },
];

/**
 * Claude 模型配置
 */
const claudeModels: ModelConfig[] = [
  {
    id: 'claude-sonnet-4-5-20250929',
    displayName: 'Sonnet 4.5 (Default)',
    description: '$3/$15 per Mtok',
    isDefault: true,
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 60,
    isPaid: true,
    speedTier: 'medium',
  },
  {
    id: 'claude-opus-4-6-20250918',
    displayName: 'Opus 4.6',
    description: 'Most capable for complex work · $5/$25 per Mtok',
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 120,
    isPaid: true,
    speedTier: 'slow',
  },
  {
    id: 'claude-opus-4-6-20250918-1m',
    displayName: 'Opus 4.6 (1M context)',
    description: 'For long sessions · $10/$37.50 per Mtok',
    capabilities: ['code', 'reasoning'],
    estimatedResponseTime: 120,
    isPaid: true,
    speedTier: 'slow',
  },
  {
    id: 'claude-haiku-4-5-20251001',
    displayName: 'Haiku 4.5',
    description: 'Fastest for quick answers · $1/$5 per Mtok',
    capabilities: ['code'],
    estimatedResponseTime: 30,
    isPaid: true,
    speedTier: 'fast',
  },
];

/**
 * 完整的模型注册表
 * Complete model registry mapping each provider to its models
 */
export const MODEL_REGISTRY: ProviderModels[] = [
  {
    provider: 'codex',
    models: codexModels,
    defaultModelId: 'gpt-5.2-codex',
  },
  {
    provider: 'gemini',
    models: geminiModels,
    defaultModelId: 'gemini-2.5-flash',
  },
  {
    provider: 'kimi',
    models: kimiModels,
    defaultModelId: 'kimi-normal',
  },
  {
    provider: 'qwen',
    models: qwenModels,
    defaultModelId: 'qwen3-coder-plus',
  },
  {
    provider: 'iflow',
    models: iflowModels,
    defaultModelId: 'iflow-normal',
  },
  {
    provider: 'ollama',
    models: ollamaModels,
    defaultModelId: 'qwen2.5:7b',
  },
  {
    provider: 'opencode',
    models: opencodeModels,
    defaultModelId: 'minimax-cn-coding-plan/MiniMax-M2.5',
  },
  {
    provider: 'goose',
    models: gooseModels,
    defaultModelId: 'goose-default',
  },
  {
    provider: 'auggie',
    models: auggieModels,
    defaultModelId: 'auggie-default',
  },
  {
    provider: 'copilot',
    models: copilotModels,
    defaultModelId: 'copilot-default',
  },
  {
    provider: 'qoder',
    models: qoderModels,
    defaultModelId: 'qoder-default',
  },
  {
    provider: 'claude',
    models: claudeModels,
    defaultModelId: 'claude-sonnet-4-20250514',
  },
  {
    provider: 'openclaw-gateway',
    models: openclawModels,
    defaultModelId: 'openclaw-default',
  },
  {
    provider: 'custom',
    models: customModels,
    defaultModelId: 'custom-default',
  },
];

/**
 * 根据 Provider 名称获取模型列表
 * Get models by provider name
 */
export function getModelsByProvider(provider: string): ModelConfig[] {
  const providerModels = MODEL_REGISTRY.find((pm) => pm.provider === provider);
  return providerModels?.models || [];
}

/**
 * 根据 Provider 和 Model ID 获取模型配置
 * Get model config by provider and model ID
 */
export function getModelConfig(provider: string, modelId: string): ModelConfig | undefined {
  const models = getModelsByProvider(provider);
  return models.find((m) => m.id === modelId);
}

/**
 * 获取 Provider 的默认模型 ID
 * Get default model ID for a provider
 */
export function getDefaultModelId(provider: string): string | undefined {
  const providerModels = MODEL_REGISTRY.find((pm) => pm.provider === provider);
  return providerModels?.defaultModelId;
}

/**
 * 获取所有支持的 Provider 列表
 * Get all supported providers
 */
export function getAllProviders(): string[] {
  return MODEL_REGISTRY.map((pm) => pm.provider);
}
