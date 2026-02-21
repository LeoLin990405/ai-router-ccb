/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { ipcBridge } from '@/common';
import type { AcpBackend, ModelConfig } from '@/types/acpTypes';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/renderer/components/ui/select';
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';

// 默认模型列表
const DEFAULT_MODELS: Partial<Record<AcpBackend, ModelConfig[]>> = {
  qwen: [
    { id: 'qwen3-coder-plus', displayName: 'Qwen3 Coder Plus', description: '代码专用模型', isDefault: true },
    { id: 'qwen3-max-2026-01-23', displayName: 'Qwen3 Max (思考)', description: '启用思考链' },
  ],
  kimi: [
    { id: 'kimi-normal', displayName: 'Kimi 标准模式', description: '快速响应', isDefault: true },
    { id: 'kimi-thinking', displayName: 'Kimi 思考模式', description: '详细推理' },
  ],
  ollama: [
    { id: 'qwen2.5:7b', displayName: 'Qwen 2.5 7B', description: '推荐模型', isDefault: true },
    { id: 'llama3.2:3b', displayName: 'Llama 3.2 3B', description: '轻量模型' },
  ],
  iflow: [
    { id: 'iflow-normal', displayName: 'iFlow 标准模式', description: '工作流自动化', isDefault: true },
    { id: 'iflow-thinking', displayName: 'iFlow 思考模式', description: '启用思考链' },
  ],
  opencode: [
    { id: 'minimax-cn-coding-plan/MiniMax-M2.5', displayName: 'MiniMax M2.5 付费', description: '能力更强', isDefault: true },
    { id: 'opencode/minimax-m2.5-free', displayName: 'MiniMax M2.5 免费', description: '免费模型' },
  ],
  codex: [
    { id: 'o3', displayName: 'o3 深度推理', description: '最强推理能力', isDefault: true },
    { id: 'o4-mini', displayName: 'o4-mini', description: '快速推理' },
  ],
  claude: [
    { id: 'claude-sonnet-4-20250514', displayName: 'Claude Sonnet 4', description: '快速且智能', isDefault: true },
    { id: 'claude-opus-4-20250514', displayName: 'Claude Opus 4', description: '最强推理' },
  ],
};

interface AcpModelSelectorProps {
  conversationId: string;
  backend: AcpBackend;
  currentModelId?: string;
}

const AcpModelSelector: React.FC<AcpModelSelectorProps> = ({ conversationId, backend, currentModelId }) => {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(currentModelId || '');
  const [loading, setLoading] = useState(true);

  // 加载模型列表
  useEffect(() => {
    const loadModels = async () => {
      setLoading(true);
      try {
        const modelList = await ipcBridge.models.getModels.invoke({ provider: backend });
        if (Array.isArray(modelList) && modelList.length > 0) {
          setModels(modelList);
          // 如果没有当前模型，选择默认模型
          if (!currentModelId && modelList.length > 0) {
            const defaultModel = modelList.find(m => m.isDefault) || modelList[0];
            setSelectedModel(defaultModel.id);
          }
        } else {
          // 使用默认模型
          const defaults = DEFAULT_MODELS[backend] || [];
          setModels(defaults);
          if (!currentModelId && defaults.length > 0) {
            const defaultModel = defaults.find(m => m.isDefault) || defaults[0];
            setSelectedModel(defaultModel.id);
          }
        }
      } catch (error) {
        console.error('[AcpModelSelector] Failed to load models:', error);
        // 使用默认模型
        const defaults = DEFAULT_MODELS[backend] || [];
        setModels(defaults);
      } finally {
        setLoading(false);
      }
    };
    loadModels();
  }, [backend, currentModelId]);

  // 同步当前模型
  useEffect(() => {
    if (currentModelId) {
      setSelectedModel(currentModelId);
    }
  }, [currentModelId]);

  // 处理模型选择
  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    try {
      // 更新会话的 modelId
      await ipcBridge.conversation.update.invoke({
        id: conversationId,
        updates: {
          extra: {
            modelId: modelId,
          },
        } as any,
      });
      toast.success('模型已更新');
    } catch (error) {
      console.error('[AcpModelSelector] Failed to update model:', error);
      toast.error('更新模型失败');
    }
  };

  // 如果只有一个模型或没有模型，不显示选择器
  if (!loading && models.length <= 1) {
    return null;
  }

  // 获取显示名称
  const selectedModelConfig = models.find(m => m.id === selectedModel);
  const displayName = selectedModelConfig?.displayName || selectedModel || backend;

  return (
    <div className='flex items-center gap-2'>
      <Select value={selectedModel || undefined} onValueChange={handleModelChange} disabled={loading}>
        <SelectTrigger className='h-7 text-xs w-[160px]'>
          <SelectValue placeholder={loading ? '加载中...' : '选择模型'}>
            <span className='truncate'>{loading ? '加载中...' : displayName}</span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {models.map((model) => (
            <SelectItem key={model.id} value={model.id} className='text-xs'>
              <div className='flex flex-col gap-0.5'>
                <div className='flex items-center gap-2'>
                  <span>{model.displayName}</span>
                  {model.isDefault && (
                    <span className='text-[10px] px-1 py-0.5 bg-primary/10 text-primary rounded'>默认</span>
                  )}
                </div>
                {model.description && <span className='text-[10px] text-t-secondary'>{model.description}</span>}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};

export default AcpModelSelector;
