import React, { useEffect, useMemo, useState } from 'react';
import { ipcBridge } from '@/common';
import { MODEL_REGISTRY } from '@/common/models/modelRegistry';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/renderer/components/ui/select';
import type { AcpBackendAll, ModelConfig } from '@/types/acpTypes';
import classNames from 'classnames';

interface ModelSelectorProps {
  provider: AcpBackendAll;
  value?: string | null;
  onChange?: (modelId: string) => void;
  disabled?: boolean;
  className?: string;
}

// 从 MODEL_REGISTRY 动态获取默认模型列表（单一数据源）
// Get default models from MODEL_REGISTRY (single source of truth)
const getDefaultModels = (provider: AcpBackendAll): ModelConfig[] => {
  const entry = MODEL_REGISTRY.find((e) => e.provider === provider);
  return entry?.models || [{ id: `${provider}-default`, displayName: `${provider} 默认`, isDefault: true }];
};

/**
 * 通用模型选择器组件
 * Universal Model Selector Component
 */
const ModelSelector: React.FC<ModelSelectorProps> = ({ provider, value, onChange, disabled = false, className }) => {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>(value ?? '');

  // Sync value prop with internal state
  useEffect(() => {
    if (value) {
      setSelectedModel(value);
    }
  }, [value]);

  // Load models when provider changes
  useEffect(() => {
    let disposed = false;
    const timeoutId = setTimeout(() => {
      // 5秒超时，使用默认模型
      if (!disposed && loading) {
        console.warn(`[ModelSelector] Timeout loading models for ${provider}, using defaults`);
        const defaultModels = getDefaultModels(provider);
        setModels(defaultModels);
        setLoading(false);
        setError(null);
      }
    }, 5000);

    const loadModels = async () => {
      setLoading(true);
      setError(null);
      console.log(`[ModelSelector] Loading models for provider: ${provider}`);

      try {
        const modelList = await ipcBridge.models.getModels.invoke({ provider });
        console.log(`[ModelSelector] Received models for ${provider}:`, modelList);

        if (disposed) return;

        clearTimeout(timeoutId);

        if (!Array.isArray(modelList) || modelList.length === 0) {
          console.log(`[ModelSelector] No models returned, using defaults for ${provider}`);
          const defaultModels = getDefaultModels(provider);
          setModels(defaultModels);
        } else {
          setModels(modelList);
        }

        // Auto-select default model if no model is selected
        const currentModels = Array.isArray(modelList) && modelList.length > 0 ? modelList : getDefaultModels(provider);
        if (currentModels.length > 0) {
          const current = value ?? selectedModel;
          const currentExists = current ? currentModels.some((model) => model.id === current) : false;

          if (!currentExists) {
            const defaultModel = currentModels.find((model) => model.isDefault) ?? currentModels[0];
            if (defaultModel) {
              console.log(`[ModelSelector] Auto-selecting default model: ${defaultModel.id}`);
              setSelectedModel(defaultModel.id);
              if (!value) {
                onChange?.(defaultModel.id);
              }
            }
          }
        }
      } catch (err) {
        if (disposed) return;
        console.error(`[ModelSelector] Failed to load models for ${provider}:`, err);
        // 使用默认模型，不阻止用户操作
        const defaultModels = getDefaultModels(provider);
        setModels(defaultModels);
        setError(null); // 不显示错误，因为已经有默认值可用
      } finally {
        if (!disposed) {
          setLoading(false);
          clearTimeout(timeoutId);
        }
      }
    };

    void loadModels();

    return () => {
      disposed = true;
      clearTimeout(timeoutId);
    };
  }, [provider]);

  // Handle model selection change
  const handleModelChange = (modelId: string) => {
    console.log(`[ModelSelector] Model changed to: ${modelId}`);
    setSelectedModel(modelId);
    onChange?.(modelId);
  };

  // Get display label for selected model
  const selectedLabel = useMemo(() => {
    if (!selectedModel) return null;
    const found = models.find((model) => model.id === selectedModel);
    return found?.displayName ?? selectedModel;
  }, [models, selectedModel]);

  // Get provider display name
  const providerDisplayName = useMemo(() => {
    const names: Partial<Record<AcpBackendAll, string>> = {
      ollama: 'Ollama',
      claude: 'Claude',
      gemini: 'Gemini',
      qwen: 'Qwen',
      kimi: 'Kimi',
      codex: 'Codex',
      iflow: 'iFlow',
      opencode: 'OpenCode',
      goose: 'Goose',
      auggie: 'Auggie',
      copilot: 'Copilot',
      qoder: 'Qoder',
      'openclaw-gateway': 'OpenClaw',
      custom: 'Custom',
    };
    return names[provider] ?? provider;
  }, [provider]);

  // Determine placeholder text based on state
  const getPlaceholder = () => {
    if (models.length === 0 && loading) return `Loading...`;
    if (models.length === 0) return `Select model`;
    return `Select ${providerDisplayName} model`;
  };

  // 只有在明确禁用时才禁用，不在加载时禁用
  const isDisabled = disabled;

  return (
    <div className={className}>
      <Select value={selectedModel || undefined} onValueChange={handleModelChange} disabled={isDisabled}>
        <SelectTrigger
          className={classNames(
            'hive-model-selector-trigger h-7 text-xs',
            className ? '' : 'w-[180px]',
            models.length === 0 && 'opacity-60'
          )}
        >
          <SelectValue placeholder={getPlaceholder()}>
            {selectedLabel ? (
              <span className='truncate'>{selectedLabel}</span>
            ) : (
              <span className='truncate text-t-secondary'>{getPlaceholder()}</span>
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent className='hive-model-selector-content'>
          {models.length === 0 ? (
            <div className='px-2 py-3 text-xs text-center text-t-secondary'>
              {loading ? 'Loading...' : `No models found`}
            </div>
          ) : (
            models.map((model) => (
              <SelectItem key={model.id} value={model.id} className='text-xs'>
                <div className='flex flex-col gap-0.5'>
                  <div className='flex items-center gap-2'>
                    <span>{model.displayName}</span>
                    {model.isDefault && (
                      <span className='text-[10px] px-1 py-0.5 bg-primary/10 text-primary rounded'>Default</span>
                    )}
                  </div>
                  {model.description && <span className='text-[10px] text-t-secondary'>{model.description}</span>}
                </div>
              </SelectItem>
            ))
          )}
        </SelectContent>
      </Select>
    </div>
  );
};

export default ModelSelector;
