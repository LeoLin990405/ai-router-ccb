/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { HIVEMIND_PROVIDER_OPTIONS } from '@/agent/hivemind/types';
import { ipcBridge } from '@/common';
import type { AcpBackendAll, UserModelPreferences } from '@/types/acpTypes';
import ModelSelector from '@/renderer/components/ModelSelector';
import { emitter } from '@/renderer/utils/emitter';
import React, { useCallback, useEffect, useMemo, useState } from 'react';

const MODEL_SELECTABLE_PROVIDERS = new Set<AcpBackendAll>([
  'claude', 'codex', 'gemini', 'kimi', 'qwen',
  'iflow', 'opencode', 'ollama', 'goose', 'auggie', 'copilot',
  'qoder', 'openclaw-gateway', 'custom',
]);

const isModelSelectable = (provider: string | null | undefined): provider is AcpBackendAll => {
  if (!provider || provider.startsWith('@')) return false;
  return MODEL_SELECTABLE_PROVIDERS.has(provider as AcpBackendAll);
};

const isValidModelId = (modelId: string | null | undefined): modelId is string => {
  if (!modelId || modelId.trim() === '') return false;
  const t = modelId.trim().toLowerCase();
  if (new Set(['auto', 'default', 'none', '']).has(t)) return false;
  if (t.endsWith('-default')) return false;
  return true;
};

interface Props {
  conversationId: string;
}

const HivemindModelSelector: React.FC<Props> = ({ conversationId }) => {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [userModelPrefs, setUserModelPrefs] = useState<UserModelPreferences>({ selectedModels: {} });

  // Load conversation's default provider
  useEffect(() => {
    void ipcBridge.conversation.get.invoke({ id: conversationId }).then((conv) => {
      const extra = conv?.extra as { defaultProvider?: string | null } | undefined;
      if (extra?.defaultProvider) {
        setSelectedProvider(extra.defaultProvider);
      }
    });
  }, [conversationId]);

  // Load model preferences
  useEffect(() => {
    let disposed = false;
    void ipcBridge.models.getUserPreferences.invoke().then((prefs) => {
      if (!disposed) setUserModelPrefs({ selectedModels: prefs.selectedModels || {} });
    });
    return () => { disposed = true; };
  }, []);

  // Sync provider/model changes from SendBox
  useEffect(() => {
    const handler = ({ provider, modelId }: { provider: string; modelId: string }) => {
      setSelectedProvider(provider);
      if (isModelSelectable(provider)) {
        setUserModelPrefs((prev) => ({
          selectedModels: { ...prev.selectedModels, [provider]: modelId },
        }));
      }
    };
    emitter.on('hivemind.model.changed', handler);
    return () => { emitter.off('hivemind.model.changed', handler); };
  }, []);

  const handleModelChange = useCallback(
    async (provider: AcpBackendAll, modelId: string) => {
      if (!isValidModelId(modelId)) return;
      const next: UserModelPreferences = {
        selectedModels: { ...(userModelPrefs.selectedModels || {}), [provider]: modelId },
      };
      setUserModelPrefs(next);
      emitter.emit('hivemind.model.changed', { provider, modelId });
      try {
        await ipcBridge.models.saveUserPreferences.invoke(next);
      } catch (error) {
        console.error('[HivemindModelSelector] Failed to save model:', error);
      }
    },
    [userModelPrefs]
  );

  const providerLabel = useMemo(() => {
    const opt = HIVEMIND_PROVIDER_OPTIONS.find((o) => o.value === selectedProvider);
    return opt?.label ?? selectedProvider ?? 'Auto';
  }, [selectedProvider]);

  const showModelSelector = isModelSelectable(selectedProvider);
  const rawModelId = showModelSelector ? (userModelPrefs.selectedModels?.[selectedProvider] ?? null) : null;
  const validModelId = isValidModelId(rawModelId) ? rawModelId : null;

  return (
    <div className='flex items-center gap-1.5'>
      <span className='text-xs text-t-secondary truncate max-w-[80px]'>{providerLabel}</span>
      {showModelSelector && (
        <ModelSelector
          provider={selectedProvider}
          value={validModelId}
          onChange={(modelId) => void handleModelChange(selectedProvider, modelId)}
          className='w-[160px]'
        />
      )}
    </div>
  );
};

export default HivemindModelSelector;
