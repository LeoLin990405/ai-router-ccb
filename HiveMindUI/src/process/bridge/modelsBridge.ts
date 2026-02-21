import type { UserModelPreferences, AcpBackendAll } from '@/types/acpTypes';
import { getModelsByProvider, getDefaultModelId } from '@/common/models/modelRegistry';
import { ollamaService } from '@/process/services/ollama/OllamaService';
import { scanModelsForProvider, prescanAllProviders } from '@/process/services/cliModelScanner';
import { ConfigStorage } from '@/common/storage';

// Dynamic Electron import for ipcMain
let _ipcMain: typeof import('electron').ipcMain | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  _ipcMain = require('electron').ipcMain;
  if (typeof _ipcMain?.handle !== 'function') _ipcMain = null;
} catch {
  _ipcMain = null;
}

/**
 * 默认 Ollama 模型列表（当 Ollama 服务不可用或没有模型时的回退）
 * Default Ollama models (fallback when Ollama service is unavailable or has no models)
 */
const OLLAMA_FALLBACK_MODELS = [
  { id: 'qwen2.5:7b', displayName: 'Qwen 2.5 7B', description: 'Qwen 2.5 7B 模型', isDefault: true },
  { id: 'llama3.2:3b', displayName: 'Llama 3.2 3B', description: 'Llama 3.2 3B 轻量模型' },
  { id: 'codellama:7b', displayName: 'Code Llama 7B', description: 'Code Llama 代码模型' },
];

export function initModelsBridge(): void {
  // In standalone mode without ipcMain, these direct IPC handlers are not needed
  // The bridge library handlers (via ipcBridge) still work through Socket.IO
  if (!_ipcMain) {
    // Still run pre-scan for CLI models
    prescanAllProviders().catch((err) => {
      console.warn('[modelsBridge] Pre-scan failed:', err);
    });
    return;
  }

  const channels = ['models:getModels', 'models:getOllamaModels', 'models:getUserPreferences', 'models:saveUserPreferences', 'models:getDefaultModel'];
  channels.forEach((channel) => {
    _ipcMain!.removeHandler(channel);
  });

  // 启动时异步预扫描所有 CLI 模型（不阻塞）
  prescanAllProviders().catch((err) => {
    console.warn('[modelsBridge] Pre-scan failed:', err);
  });

  _ipcMain!.handle('models:getModels', async (_, params: { provider: AcpBackendAll }) => {
    const provider = params.provider;
    console.log(`[modelsBridge] getModels called for provider: ${provider}`);

    // Special handling for Ollama - try dynamic fetch first
    if (provider === 'ollama') {
      try {
        const dynamicModels = await ollamaService.listModels();
        if (dynamicModels.length > 0) {
          console.log(`[modelsBridge] Ollama: Found ${dynamicModels.length} models from service`);
          return dynamicModels;
        }
      } catch (err) {
        console.warn('[modelsBridge] Ollama service unavailable, using fallback models:', err);
      }

      // Fallback to registry, then to hardcoded list
      const registryModels = getModelsByProvider('ollama');
      if (registryModels.length > 0) {
        console.log(`[modelsBridge] Ollama: Using ${registryModels.length} models from registry`);
        return registryModels;
      }

      console.log('[modelsBridge] Ollama: Using fallback model list');
      return OLLAMA_FALLBACK_MODELS;
    }

    // 其他 Provider: 优先从 CLI 配置扫描，回退到 registry
    // Other providers: scan from CLI config first, fallback to registry
    const models = await scanModelsForProvider(provider);
    console.log(`[modelsBridge] ${provider}: Found ${models.length} models (via scanner):`, models.map(m => m.id));
    return models;
  });

  _ipcMain!.handle('models:getOllamaModels', async () => {
    try {
      return await ollamaService.listModels();
    } catch {
      return OLLAMA_FALLBACK_MODELS;
    }
  });

  _ipcMain!.handle('models:getUserPreferences', async () => {
    const config = (await ConfigStorage.get('hivemind.userModelPreferences')) as { selectedModels?: Record<string, string>; lastUpdated?: string } | undefined;
    return {
      selectedModels: config?.selectedModels || {},
      lastUpdated: config?.lastUpdated,
    };
  });

  _ipcMain!.handle('models:saveUserPreferences', async (_, preferences: UserModelPreferences) => {
    await ConfigStorage.set('hivemind.userModelPreferences', {
      selectedModels: preferences.selectedModels,
      lastUpdated: new Date().toISOString(),
    });
  });

  _ipcMain!.handle('models:getDefaultModel', async (_, params: { provider: AcpBackendAll }) => {
    const provider = params.provider;

    // For Ollama, try dynamic first
    if (provider === 'ollama') {
      try {
        const dynamicModels = await ollamaService.listModels();
        if (dynamicModels.length > 0) {
          const defaultModel = dynamicModels.find((m) => m.isDefault) || dynamicModels[0];
          return defaultModel || null;
        }
      } catch {
        // Fall through to registry/fallback
      }
    }

    // 优先从扫描结果获取
    const scannedModels = await scanModelsForProvider(provider);
    if (scannedModels.length > 0) {
      const found = scannedModels.find((m) => m.isDefault) || scannedModels[0];
      return found || null;
    }

    // Try registry
    const defaultId = getDefaultModelId(provider);
    const models = getModelsByProvider(provider);
    const found = models.find((m) => m.id === defaultId) || models.find((m) => m.isDefault) || models[0];

    // For Ollama, also check fallback
    if (!found && provider === 'ollama') {
      return OLLAMA_FALLBACK_MODELS[0] || null;
    }

    return found || null;
  });
}
