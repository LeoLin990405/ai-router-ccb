/**
 * CLI Model Scanner - 通过 shell 脚本从各 CLI 动态扫描可用模型
 * Dynamically scans available models from each CLI via shell script
 *
 * 扫描方式:
 * - Codex: 从二进制文件提取嵌入的模型数据
 * - Claude: 从二进制文件提取模型 ID
 * - OpenCode: `opencode models` 命令
 * - Qwen: ~/.qwen/settings.json
 * - Kimi: ~/.kimi/config.toml
 * - iFlow: ~/.iflow/settings.json
 * - Ollama: `ollama list` 命令
 */

import { execFile } from 'child_process';
import * as path from 'path';
import * as paths from '@/process/paths';
import { getModelsByProvider } from '@/common/models/modelRegistry';
import type { ModelConfig } from '@/types/acpTypes';

// Dynamic Electron import
let _electronApp: typeof import('electron').app | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  _electronApp = require('electron').app;
  if (typeof _electronApp?.getAppPath !== 'function') _electronApp = null;
} catch {
  _electronApp = null;
}

/** 缓存：provider → models */
const modelCache = new Map<string, { models: ModelConfig[]; scannedAt: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 分钟缓存

/** 获取 scanner 脚本路径（兼容开发和打包模式） */
function getScannerPath(): string {
  const appPath = _electronApp ? _electronApp.getAppPath() : paths.getAppRootPath();
  return path.join(appPath, 'scripts', 'scan-cli-models.sh');
}

/**
 * 调用 scan-cli-models.sh 脚本扫描指定 Provider 的模型
 */
function runScanner(provider: string): Promise<ModelConfig[]> {
  return new Promise((resolve) => {
    const scriptPath = getScannerPath();
    execFile('bash', [scriptPath, provider], { timeout: 15000, encoding: 'utf-8' }, (err, stdout) => {
      if (err) {
        console.warn(`[CliModelScanner] Script error for ${provider}:`, err.message);
        resolve([]);
        return;
      }
      try {
        const models = JSON.parse(stdout.trim());
        if (Array.isArray(models)) {
          resolve(models);
        } else {
          resolve([]);
        }
      } catch (parseErr) {
        console.warn(`[CliModelScanner] JSON parse error for ${provider}:`, parseErr);
        resolve([]);
      }
    });
  });
}

/**
 * 扫描指定 Provider 的可用模型
 * 优先从 CLI 动态扫描，失败则回退到 MODEL_REGISTRY
 */
export async function scanModelsForProvider(provider: string): Promise<ModelConfig[]> {
  // 检查缓存
  const cached = modelCache.get(provider);
  if (cached && Date.now() - cached.scannedAt < CACHE_TTL_MS) {
    return cached.models;
  }

  let models: ModelConfig[] = [];

  try {
    models = await runScanner(provider);
    if (models.length > 0) {
      console.log(`[CliModelScanner] ${provider}: scanned ${models.length} models from CLI`);
    }
  } catch (err) {
    console.warn(`[CliModelScanner] Failed to scan ${provider}:`, err);
  }

  // 如果扫描结果为空，回退到 MODEL_REGISTRY
  if (models.length === 0) {
    models = getModelsByProvider(provider);
    if (models.length > 0) {
      console.log(`[CliModelScanner] ${provider}: using ${models.length} models from registry (fallback)`);
    }
  }

  // 缓存结果
  if (models.length > 0) {
    modelCache.set(provider, { models, scannedAt: Date.now() });
  }

  return models;
}

/**
 * 清除指定 Provider 的缓存（或全部）
 */
export function clearModelCache(provider?: string): void {
  if (provider) {
    modelCache.delete(provider);
  } else {
    modelCache.clear();
  }
}

/**
 * 启动时预扫描所有 Provider（异步，不阻塞启动）
 */
export async function prescanAllProviders(): Promise<void> {
  const providers = ['codex', 'claude', 'qwen', 'kimi', 'opencode', 'iflow', 'ollama'];
  console.log('[CliModelScanner] Pre-scanning all providers...');

  const results = await Promise.allSettled(
    providers.map(async (p) => {
      const models = await scanModelsForProvider(p);
      return { provider: p, count: models.length };
    })
  );

  const summary = results
    .filter((r): r is PromiseFulfilledResult<{ provider: string; count: number }> => r.status === 'fulfilled')
    .map((r) => `${r.value.provider}(${r.value.count})`)
    .join(', ');
  console.log(`[CliModelScanner] Pre-scan complete: ${summary}`);
}
