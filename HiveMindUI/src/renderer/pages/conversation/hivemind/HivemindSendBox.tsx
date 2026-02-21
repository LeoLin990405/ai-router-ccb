/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { DEFAULT_HIVEMIND_CONFIG, HIVEMIND_PROVIDER_OPTIONS } from '@/agent/hivemind/types';
import { ipcBridge } from '@/common';
import type { TMessage } from '@/common/chatLib';
import { transformMessage } from '@/common/chatLib';
import type { TokenUsageData } from '@/common/storage';
import { uuid } from '@/common/utils';
import ContextUsageIndicator from '@/renderer/components/ContextUsageIndicator';
import FilePreview from '@/renderer/components/FilePreview';
import HorizontalFileList from '@/renderer/components/HorizontalFileList';
import ThoughtDisplay, { type ThoughtData } from '@/renderer/components/ThoughtDisplay';
import SendBox from '@/renderer/components/sendbox';
import ModelSelector from '@/renderer/components/ModelSelector';
import { useAutoTitle } from '@/renderer/hooks/useAutoTitle';
import { useLatestRef } from '@/renderer/hooks/useLatestRef';
import { useHivemindStatus } from '@/renderer/hooks/useHivemindStatus';
import { getSendBoxDraftHook, type FileOrFolderItem } from '@/renderer/hooks/useSendBoxDraft';
import { useAddOrUpdateMessage } from '@/renderer/messages/hooks';
import { usePreviewContext } from '@/renderer/pages/conversation/preview';
import { allSupportedExts, type FileMetadata } from '@/renderer/services/FileService';
import { tokens } from '@/renderer/design-tokens';
import { getModelContextLimit } from '@/renderer/utils/modelContextLimits';
import { iconColors } from '@/renderer/theme/colors';
import { emitter, useAddEventListener } from '@/renderer/utils/emitter';
import { buildDisplayMessage, collectSelectedFiles } from '@/renderer/utils/messageFiles';
import { mergeFileSelectionItems } from '@/renderer/utils/fileSelection';
import { Button } from '@/renderer/components/ui/button';
import { Badge } from '@/renderer/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/renderer/components/ui/select';
import { toast } from 'sonner';
import type { AcpBackendAll, UserModelPreferences } from '@/types/acpTypes';
import { Plus, X } from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import HivemindProviderBadge from './HivemindProviderBadge';
import HivemindRoutingInfo from './HivemindRoutingInfo';

const useHivemindSendBoxDraft = getSendBoxDraftHook('hivemind', {
  _type: 'hivemind',
  atPath: [],
  content: '',
  uploadFile: [],
  selectedProvider: null,
});

const MODEL_SELECTABLE_PROVIDERS = new Set<AcpBackendAll>(['claude', 'codex', 'gemini', 'kimi', 'qwen', 'iflow', 'opencode', 'ollama', 'goose', 'auggie', 'copilot', 'qoder', 'openclaw-gateway', 'custom']);

const isModelSelectableProvider = (provider: string | null | undefined): provider is AcpBackendAll => {
  if (!provider) return false;
  if (provider.startsWith('@')) return false;
  return MODEL_SELECTABLE_PROVIDERS.has(provider as AcpBackendAll);
};

/**
 * 验证模型 ID 是否有效（过滤掉 "auto", "default" 等占位符）
 * Validate if model ID is valid (filter out "auto", "default" placeholders)
 */
const isValidModelId = (modelId: string | null | undefined): modelId is string => {
  if (!modelId || modelId.trim() === '') return false;
  const trimmed = modelId.trim().toLowerCase();

  // 无效模型名称列表（占位符和默认值）
  const invalidModels = new Set(['auto', 'default', 'none', '']);
  if (invalidModels.has(trimmed)) return false;

  // 以 "-default" 结尾的是注册表占位符
  if (trimmed.endsWith('-default')) return false;

  return true;
};

/**
 * 获取有效的模型 ID，如果无效则返回 null
 * Get valid model ID, return null if invalid
 */
const getValidModel = (modelId: string | null | undefined): string | null => {
  return isValidModelId(modelId) ? modelId!.trim() : null;
};

const HivemindSendBox: React.FC<{ conversation_id: string; gatewayUrl?: string }> = ({ conversation_id, gatewayUrl: gatewayUrlProp }) => {
  const { t } = useTranslation();
  const { checkAndUpdateTitle } = useAutoTitle();
  const addOrUpdateMessage = useAddOrUpdateMessage();
  const { setSendBoxHandler } = usePreviewContext();

  const [gatewayUrl, setGatewayUrl] = useState(() => gatewayUrlProp ?? DEFAULT_HIVEMIND_CONFIG.gatewayUrl);
  const { connected: gatewayConnected, providers } = useHivemindStatus(gatewayUrl);

  const [workspacePath, setWorkspacePath] = useState('');
  const [running, setRunning] = useState(false);
  const [aiProcessing, setAiProcessing] = useState(false);
  const [lastProvider, setLastProvider] = useState<string | null>(null);
  const [lastCached, setLastCached] = useState(false);
  const [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);
  const [lastTokens, setLastTokens] = useState<number | null>(null);
  const [tokenUsage, setTokenUsage] = useState<TokenUsageData | null>(null);
  const [thought, setThought] = useState<ThoughtData>({ subject: '', description: '' });
  const [userModelPreferences, setUserModelPreferences] = useState<UserModelPreferences>({ selectedModels: {} });
  const [pendingRetry, setPendingRetry] = useState<{
    message: string;
    files: string[];
    provider: string | null;
    model: string | null;
  } | null>(null);

  const busyRef = useRef(false);
  const lastSentRef = useRef<{
    message: string;
    files: string[];
    provider: string | null;
    model: string | null;
  } | null>(null);
  const exhaustedProvidersRef = useRef<Set<string>>(new Set());
  const quotaHandledMsgRef = useRef<string | null>(null);

  // Throttle thought updates to reduce render frequency
  const thoughtThrottleRef = useRef<{
    lastUpdate: number;
    pending: ThoughtData | null;
    timer: ReturnType<typeof setTimeout> | null;
  }>({ lastUpdate: 0, pending: null, timer: null });

  const throttledSetThought = useMemo(() => {
    const THROTTLE_MS = 50;
    return (data: ThoughtData) => {
      const now = Date.now();
      const ref = thoughtThrottleRef.current;
      if (now - ref.lastUpdate >= THROTTLE_MS) {
        ref.lastUpdate = now;
        ref.pending = null;
        if (ref.timer) {
          clearTimeout(ref.timer);
          ref.timer = null;
        }
        setThought(data);
        return;
      }

      ref.pending = data;
      if (!ref.timer) {
        ref.timer = setTimeout(
          () => {
            ref.lastUpdate = Date.now();
            ref.timer = null;
            if (ref.pending) {
              setThought(ref.pending);
              ref.pending = null;
            }
          },
          THROTTLE_MS - (now - ref.lastUpdate)
        );
      }
    };
  }, []);

  useEffect(() => {
    return () => {
      if (thoughtThrottleRef.current.timer) {
        clearTimeout(thoughtThrottleRef.current.timer);
      }
    };
  }, []);

  const { data, mutate } = useHivemindSendBoxDraft(conversation_id);
  const atPath = data?.atPath ?? [];
  const content = data?.content ?? '';
  const uploadFile = data?.uploadFile ?? [];
  const selectedProvider = data?.selectedProvider ?? null;

  const atPathRef = useLatestRef(atPath);
  const uploadFileRef = useLatestRef(uploadFile);
  const selectedProviderRef = useLatestRef(selectedProvider);

  const providersRef = useLatestRef(providers);
  const lastProviderRef = useLatestRef(lastProvider);
  const tRef = useLatestRef(t);

  useEffect(() => {
    let disposed = false;

    const loadModelPreferences = async () => {
      try {
        const prefs = await ipcBridge.models.getUserPreferences.invoke();
        if (disposed) return;
        setUserModelPreferences({ selectedModels: prefs.selectedModels || {}, lastUpdated: prefs.lastUpdated });
      } catch (error) {
        console.error('Failed to load model preferences:', error);
      }
    };

    void loadModelPreferences();

    return () => {
      disposed = true;
    };
  }, []);

  const handleModelChange = useCallback(
    async (provider: AcpBackendAll, modelId: string) => {
      // 验证模型 ID 是否有效
      const validModelId = getValidModel(modelId);
      if (!validModelId) {
        console.warn(`[HivemindSendBox] Invalid model ID "${modelId}" rejected for provider ${provider}`);
        return;
      }

      const nextPreferences: UserModelPreferences = {
        selectedModels: {
          ...(userModelPreferences.selectedModels || {}),
          [provider]: validModelId,
        },
      };

      setUserModelPreferences(nextPreferences);
      emitter.emit('hivemind.model.changed', { provider, modelId: validModelId });

      try {
        await ipcBridge.models.saveUserPreferences.invoke(nextPreferences);
      } catch (error) {
        console.error('Failed to save model preferences:', error);
      }
    },
    [userModelPreferences]
  );

  // Sync model changes from header selector
  useAddEventListener('hivemind.model.changed', ({ provider, modelId }: { provider: string; modelId: string }) => {
    if (isModelSelectableProvider(provider)) {
      setUserModelPreferences((prev) => ({
        selectedModels: { ...(prev.selectedModels || {}), [provider]: modelId },
      }));
    }
  }, []);

  const setContent = useCallback(
    (value: string) => {
      mutate((prev) => ({
        _type: 'hivemind',
        atPath: prev?.atPath ?? [],
        uploadFile: prev?.uploadFile ?? [],
        selectedProvider: prev?.selectedProvider ?? null,
        content: value,
      }));
    },
    [mutate]
  );

  const setAtPath = useCallback(
    (items: Array<string | FileOrFolderItem>) => {
      mutate((prev) => ({
        _type: 'hivemind',
        atPath: items,
        uploadFile: prev?.uploadFile ?? [],
        selectedProvider: prev?.selectedProvider ?? null,
        content: prev?.content ?? '',
      }));
    },
    [mutate]
  );

  const setUploadFile = useCallback(
    (value: string[]) => {
      mutate((prev) => ({
        _type: 'hivemind',
        atPath: prev?.atPath ?? [],
        uploadFile: value,
        selectedProvider: prev?.selectedProvider ?? null,
        content: prev?.content ?? '',
      }));
    },
    [mutate]
  );

  const setSelectedProvider = useCallback(
    (value: string | null) => {
      mutate((prev) => ({
        _type: 'hivemind',
        atPath: prev?.atPath ?? [],
        uploadFile: prev?.uploadFile ?? [],
        selectedProvider: value,
        content: prev?.content ?? '',
      }));
    },
    [mutate]
  );

  const setSelectedProviderRef = useLatestRef(setSelectedProvider);

  const setContentRef = useLatestRef(setContent);

  useEffect(() => {
    const handler = (text: string) => {
      const next = content ? `${content}\n${text}` : text;
      setContentRef.current(next);
    };
    setSendBoxHandler(handler);
  }, [setSendBoxHandler, content, setContentRef]);

  useAddEventListener(
    'sendbox.fill',
    (text: string) => {
      setContentRef.current(text);
    },
    []
  );

  useEffect(() => {
    setRunning(false);
    setAiProcessing(false);
    setLastProvider(null);
    setLastCached(false);
    setLastLatencyMs(null);
    setLastTokens(null);
    setTokenUsage(null);
    setThought({ subject: '', description: '' });

    busyRef.current = false;
    exhaustedProvidersRef.current.clear();
    quotaHandledMsgRef.current = null;
    lastSentRef.current = null;
    setPendingRetry(null);
  }, [conversation_id]);

  const isQuotaError = useCallback((errorText: string): boolean => {
    if (!errorText.trim()) return false;
    const text = errorText.toLowerCase();
    return text.includes('429') || text.includes('quota') || text.includes('rate_limit') || text.includes('rate limit') || text.includes('resource_exhausted') || text.includes('too many requests') || text.includes('request limit');
  }, []);

  const resolveFallbackProvider = useCallback(
    (currentProvider: string | null): string | null => {
      const priority = ['kimi', 'qwen', 'iflow', 'ollama', 'opencode', 'claude', 'codex', 'gemini'];
      const candidates = providersRef.current
        .filter((provider) => provider.enabled !== false)
        .filter((provider) => provider.status !== 'offline' && provider.status !== 'unavailable')
        .map((provider) => provider.name);

      for (const name of priority) {
        if (name === currentProvider) continue;
        if (exhaustedProvidersRef.current.has(name)) continue;
        if (candidates.includes(name)) return name;
      }

      return candidates.find((name) => name !== currentProvider && !exhaustedProvidersRef.current.has(name)) ?? null;
    },
    [providersRef]
  );

  useEffect(() => {
    if (!pendingRetry) {
      return;
    }
    if (aiProcessing || running) {
      return;
    }
    if (!gatewayConnected) {
      return;
    }

    const snapshot = pendingRetry;
    setPendingRetry(null);
    void onSendHandler(snapshot.message, {
      files: snapshot.files,
      provider: snapshot.provider,
      model: snapshot.model,
    });
  }, [pendingRetry, aiProcessing, running, gatewayConnected, userModelPreferences]);

  useEffect(() => {
    return ipcBridge.conversation.responseStream.on((message) => {
      if (message.conversation_id !== conversation_id) {
        return;
      }

      switch (message.type) {
        case 'start':
          busyRef.current = true;
          setRunning(true);
          setAiProcessing(true);
          return;
        case 'finish':
          busyRef.current = false;
          setRunning(false);
          setAiProcessing(false);
          setThought({ subject: '', description: '' });
          return;
        case 'error': {
          busyRef.current = false;
          setRunning(false);
          setAiProcessing(false);

          const errorMsg = typeof message.data === 'string' ? message.data : '';
          const msgId = typeof message.msg_id === 'string' ? message.msg_id : '';
          const lastSent = lastSentRef.current;

          if (lastSent && isQuotaError(errorMsg)) {
            if (msgId && quotaHandledMsgRef.current === msgId) {
              return;
            }
            if (msgId) {
              quotaHandledMsgRef.current = msgId;
            }

            const providerForError = lastProviderRef.current || lastSent.provider || selectedProviderRef.current;
            if (providerForError) {
              exhaustedProvidersRef.current.add(providerForError);
            }
            const fallbackProvider = resolveFallbackProvider(providerForError);
            if (fallbackProvider) {
              setSelectedProviderRef.current(fallbackProvider);
              toast.warning(
                tRef.current('hivemind.quotaSwitched', {
                  from: providerForError || 'unknown',
                  to: fallbackProvider,
                })
              );
              // 验证模型 ID，确保不传递无效值如 "auto"
              const fallbackModel = isModelSelectableProvider(fallbackProvider) ? getValidModel(userModelPreferences.selectedModels?.[fallbackProvider]) : null;
              setPendingRetry({
                message: lastSent.message,
                files: lastSent.files,
                provider: fallbackProvider,
                model: fallbackModel,
              });
              return;
            }
          }
          break;
        }
        case 'thought':
          throttledSetThought(message.data as ThoughtData);
          break;
        case 'agent_status': {
          const statusData = message.data as {
            backend?: string;
            cached?: boolean;
            latencyMs?: number | null;
            totalTokens?: number | null;
          };
          if (typeof statusData.backend === 'string' && statusData.backend.trim()) {
            setLastProvider(statusData.backend.trim());
          }
          if (typeof statusData.cached === 'boolean') {
            setLastCached(statusData.cached);
          }
          if (typeof statusData.latencyMs === 'number' && Number.isFinite(statusData.latencyMs)) {
            setLastLatencyMs(statusData.latencyMs);
          }
          if (typeof statusData.totalTokens === 'number' && statusData.totalTokens > 0) {
            setLastTokens(statusData.totalTokens);
            const newTokenUsage: TokenUsageData = { totalTokens: statusData.totalTokens };
            setTokenUsage(newTokenUsage);
            void ipcBridge.conversation.update.invoke({
              id: conversation_id,
              updates: {
                extra: {
                  lastTokenUsage: newTokenUsage,
                } as any,
              },
              mergeExtra: true,
            });
          }
          break;
        }
        default:
          break;
      }

      const transformedMessage = transformMessage(message);
      if (transformedMessage) {
        addOrUpdateMessage(transformedMessage);
      }
    });
  }, [conversation_id, addOrUpdateMessage, isQuotaError, resolveFallbackProvider]);

  useEffect(() => {
    void ipcBridge.conversation.get
      .invoke({ id: conversation_id })
      .then((conversation) => {
        if (conversation?.extra?.workspace) {
          setWorkspacePath(conversation.extra.workspace);
        }

        const extra = conversation?.extra as
          | {
              lastTokenUsage?: TokenUsageData;
              defaultProvider?: string | null;
              gatewayUrl?: string;
            }
          | undefined;

        if (extra?.gatewayUrl) {
          setGatewayUrl(extra.gatewayUrl);
        }
        if (extra?.lastTokenUsage && extra.lastTokenUsage.totalTokens > 0) {
          setTokenUsage(extra.lastTokenUsage);
          setLastTokens(extra.lastTokenUsage.totalTokens);
        }

        const defaultProvider = extra?.defaultProvider;
        if (defaultProvider && !selectedProvider) {
          setSelectedProvider(defaultProvider);
        }
      })
      .catch((error) => {
        console.error('Failed to load conversation:', error);
      });
  }, [conversation_id, selectedProvider, setSelectedProvider]);

  useEffect(() => {
    if (gatewayUrlProp) {
      setGatewayUrl(gatewayUrlProp);
    }
  }, [gatewayUrlProp]);

  const handleFilesAdded = useCallback(
    (pastedFiles: FileMetadata[]) => {
      const filePaths = pastedFiles.map((file) => file.path);
      setUploadFile([...uploadFile, ...filePaths]);
    },
    [uploadFile, setUploadFile]
  );

  // Persist selectedProvider changes to conversation.extra
  useEffect(() => {
    void ipcBridge.conversation.update.invoke({
      id: conversation_id,
      updates: {
        extra: {
          defaultProvider: selectedProvider,
        } as any,
      },
      mergeExtra: true,
    });
  }, [conversation_id, selectedProvider]);

  // Persist file selections so workspace panel selection can survive refresh
  useEffect(() => {
    const filesToSend = collectSelectedFiles(uploadFile, atPath);
    void ipcBridge.conversation.update.invoke({
      id: conversation_id,
      updates: {
        extra: {
          files: filesToSend,
        } as any,
      },
      mergeExtra: true,
    });
  }, [conversation_id, uploadFile, atPath]);

  // Workspace file selections (matching Gemini/Codex behavior)
  useAddEventListener('hivemind.selected.file', (items: Array<string | FileOrFolderItem>) => {
    setTimeout(() => {
      setAtPath(items);
    }, 10);
  });

  useAddEventListener('hivemind.selected.file.append', (items: Array<string | FileOrFolderItem>) => {
    setTimeout(() => {
      const merged = mergeFileSelectionItems(atPathRef.current, items);
      if (merged !== atPathRef.current) {
        setAtPath(merged as Array<string | FileOrFolderItem>);
      }
    }, 10);
  });

  const emitLocalError = useCallback(
    (error: string) => {
      const localErrorMessage: TMessage = {
        id: uuid(),
        msg_id: uuid(),
        conversation_id,
        type: 'tips',
        position: 'center',
        content: {
          content: error,
          type: 'error',
        },
        createdAt: Date.now(),
      };
      addOrUpdateMessage(localErrorMessage, true);
    },
    [conversation_id, addOrUpdateMessage]
  );

  const onSendHandler = async (
    message: string,
    options?: {
      files?: string[];
      provider?: string | null;
      model?: string | null;
    }
  ) => {
    if (busyRef.current) {
      return;
    }

    if (!gatewayConnected) {
      emitLocalError(t('hivemind.settings.gatewayUnreachable'));
      return;
    }

    if (!message.trim()) {
      return;
    }

    const msg_id = uuid();
    const currentUploadFiles = [...uploadFileRef.current];
    const currentProvider = options?.provider ?? selectedProviderRef.current;
    // 验证模型 ID，确保不传递无效值如 "auto"
    const rawModel = options?.model ?? (isModelSelectableProvider(currentProvider) ? (userModelPreferences.selectedModels?.[currentProvider] ?? null) : null);
    const currentModel = getValidModel(rawModel);

    setThought({ subject: '', description: '' });
    setLastTokens(null);
    setTokenUsage(null);

    setContent('');
    emitter.emit('hivemind.selected.file.clear');
    setUploadFile([]);
    setAtPath([]);
    setLastProvider(null);
    setLastCached(false);
    setLastLatencyMs(null);

    const filesToSend = options?.files ?? collectSelectedFiles(currentUploadFiles, atPathRef.current);
    lastSentRef.current = {
      message,
      files: filesToSend,
      provider: currentProvider,
      model: currentModel,
    };
    const displayMessage = buildDisplayMessage(message, filesToSend, workspacePath);

    busyRef.current = true;
    setAiProcessing(true);
    try {
      const result = await ipcBridge.conversation.sendMessage.invoke({
        input: displayMessage,
        msg_id,
        conversation_id,
        files: filesToSend,
        provider: currentProvider,
        model: currentModel,
      });

      if (!result.success) {
        emitLocalError(result.msg || 'Failed to send message');
        busyRef.current = false;
        setAiProcessing(false);
        return;
      }

      void checkAndUpdateTitle(conversation_id, message);
      emitter.emit('chat.history.refresh');
    } catch (error) {
      const normalized = error instanceof Error ? error.message : String(error);
      emitLocalError(normalized);
      busyRef.current = false;
      setAiProcessing(false);
    }
  };

  const onSendHandlerRef = useLatestRef(onSendHandler);

  useAddEventListener(
    'hivemind.regenerate',
    () => {
      const lastSent = lastSentRef.current;
      if (!lastSent || busyRef.current) return;
      void onSendHandlerRef.current(lastSent.message, { files: lastSent.files, provider: lastSent.provider, model: lastSent.model });
    },
    []
  );

  useEffect(() => {
    if (aiProcessing || running) {
      busyRef.current = true;
    }
  }, [aiProcessing, running]);

  useEffect(() => {
    const storageKey = `hivemind_initial_message_${conversation_id}`;
    const processedKey = `hivemind_initial_processed_${conversation_id}`;

    const processInitialMessage = async () => {
      const stored = sessionStorage.getItem(storageKey);
      if (!stored) {
        return;
      }
      if (sessionStorage.getItem(processedKey)) {
        return;
      }

      sessionStorage.setItem(processedKey, 'true');
      try {
        const parsed = JSON.parse(stored) as { input: string; files?: string[]; provider?: string | null; model?: string | null };
        const msg_id = uuid();
        const input = parsed.input || '';
        const files = parsed.files || [];
        const provider = typeof parsed.provider === 'string' ? parsed.provider : selectedProvider;
        // 验证模型 ID，确保不传递无效值如 "auto"
        const rawModel = typeof parsed.model === 'string' ? parsed.model : isModelSelectableProvider(provider) ? (userModelPreferences.selectedModels?.[provider] ?? null) : null;
        const model = getValidModel(rawModel);
        const displayMessage = buildDisplayMessage(input, files, workspacePath);

        busyRef.current = true;
        lastSentRef.current = {
          message: input,
          files,
          provider: provider ?? null,
          model: model ?? null,
        };
        setAiProcessing(true);
        const result = await ipcBridge.conversation.sendMessage.invoke({
          input: displayMessage,
          msg_id,
          conversation_id,
          files,
          provider,
          model,
        });

        if (!result.success) {
          throw new Error(result.msg || 'Failed to send initial message');
        }

        void checkAndUpdateTitle(conversation_id, input);
        emitter.emit('chat.history.refresh');
        sessionStorage.removeItem(storageKey);
      } catch (_error) {
        sessionStorage.removeItem(processedKey);
        busyRef.current = false;
        setAiProcessing(false);
      }
    };

    const timer = setTimeout(() => {
      processInitialMessage().catch((error) => {
        console.error('Failed to process hivemind initial message:', error);
      });
    }, 200);

    return () => {
      clearTimeout(timer);
    };
  }, [conversation_id, workspacePath, checkAndUpdateTitle, selectedProvider, userModelPreferences]);

  const getProviderHealthColor = useCallback(
    (providerValue: string): string | null => {
      if (!providerValue || providerValue.startsWith('@')) return null;
      const providerStatus = providers.find((p) => p.name === providerValue);
      if (!providerStatus) return null;
      if (providerStatus.status === 'healthy' || providerStatus.status === 'ok') return '#00b42a';
      if (providerStatus.status === 'degraded') return '#ff7d00';
      return '#f53f3f';
    },
    [providers]
  );

  const handleStop = async (): Promise<void> => {
    try {
      await ipcBridge.conversation.stop.invoke({ conversation_id });
    } finally {
      setRunning(false);
      setAiProcessing(false);
    }
  };

  const providerSelector = useMemo(
    () => (
      <Select
        value={selectedProvider ?? ''}
        onValueChange={(value: string) => {
          setSelectedProvider(value || null);
        }}
        disabled={running || aiProcessing}
      >
        <SelectTrigger
          className='w-[180px] h-7 text-xs'
          style={{
            borderRadius: tokens.radius.md,
          }}
        >
          <SelectValue placeholder={t('hivemind.selectProvider')}>
            {(() => {
              const optionValue = selectedProvider ?? '';
              const selected = HIVEMIND_PROVIDER_OPTIONS.find((opt) => opt.value === optionValue);
              const label = selected?.label ?? optionValue;
              const healthColor = getProviderHealthColor(optionValue);
              return (
                <span className='flex items-center gap-1'>
                  {healthColor && (
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        backgroundColor: healthColor,
                        display: 'inline-block',
                        flexShrink: 0,
                      }}
                    />
                  )}
                  {label}
                </span>
              );
            })()}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {HIVEMIND_PROVIDER_OPTIONS.map((opt) => {
            const healthColor = getProviderHealthColor(opt.value);
            return (
              <SelectItem key={opt.value} value={opt.value} className='text-xs'>
                <span className='flex items-center gap-1'>
                  {healthColor && (
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        backgroundColor: healthColor,
                        display: 'inline-block',
                        flexShrink: 0,
                      }}
                    />
                  )}
                  {opt.label}
                </span>
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    ),
    [selectedProvider, running, aiProcessing, gatewayConnected, setSelectedProvider, getProviderHealthColor, t]
  );

  const selectedContextLimit = useMemo(() => {
    if (!isModelSelectableProvider(selectedProvider)) return undefined;
    const modelId = userModelPreferences.selectedModels?.[selectedProvider] ?? null;
    return getModelContextLimit(modelId);
  }, [selectedProvider, userModelPreferences]);

  const modelSelector = useMemo(() => {
    if (!isModelSelectableProvider(selectedProvider)) {
      return null;
    }

    // 验证模型 ID 是否有效
    const rawModelId = userModelPreferences.selectedModels?.[selectedProvider] ?? null;
    const validModelId = getValidModel(rawModelId);

    return (
      <ModelSelector
        provider={selectedProvider}
        value={validModelId}
        onChange={(modelId) => {
          void handleModelChange(selectedProvider, modelId);
        }}
        disabled={running || aiProcessing || !gatewayConnected}
        className='w-[220px]'
      />
    );
  }, [selectedProvider, userModelPreferences, running, aiProcessing, gatewayConnected, handleModelChange]);

  const sendButtonPrefix = useMemo(() => {
    return (
      <>
        <ContextUsageIndicator tokenUsage={tokenUsage} contextLimit={selectedContextLimit} showWhenEmpty size={24} />
        {providerSelector}
        {modelSelector}
      </>
    );
  }, [providerSelector, modelSelector, tokenUsage, selectedContextLimit]);

  return (
    <div className='max-w-800px w-full mx-auto flex flex-col mb-16px'>
      <HivemindRoutingInfo requestedProvider={selectedProvider} actualProvider={lastProvider} />
      {lastProvider && <HivemindProviderBadge provider={lastProvider} cached={lastCached} latencyMs={lastLatencyMs} totalTokens={lastTokens} />}

      <ThoughtDisplay thought={thought} running={aiProcessing} style='compact' onStop={handleStop} />

      <SendBox
        value={content}
        onChange={setContent}
        loading={running || aiProcessing}
        disabled={aiProcessing || !gatewayConnected}
        className='z-10'
        placeholder={aiProcessing ? t('hivemind.processing') : t('hivemind.placeholder')}
        onStop={handleStop}
        onFilesAdded={handleFilesAdded}
        supportedExts={allSupportedExts}
        sendButtonPrefix={sendButtonPrefix}
        defaultMultiLine={true}
        lockMultiLine={true}
        tools={
          <Button
            variant='secondary'
            size='icon'
            className='rounded-full'
            onClick={() => {
              void ipcBridge.dialog.showOpen.invoke({ properties: ['openFile', 'multiSelections'] }).then((files) => {
                if (!files?.length) {
                  return;
                }
                setUploadFile([...uploadFile, ...files]);
              });
            }}
          >
            <Plus size={14} strokeWidth={2} color={iconColors.primary} />
          </Button>
        }
        prefix={
          <>
            {/* Files on top */}
            {(uploadFile.length > 0 || atPath.some((item) => (typeof item === 'string' ? true : item.isFile))) && (
              <HorizontalFileList>
                {uploadFile.map((path) => (
                  <FilePreview key={path} path={path} onRemove={() => setUploadFile(uploadFile.filter((v) => v !== path))} />
                ))}
                {atPath.map((item) => {
                  const isFile = typeof item === 'string' ? true : item.isFile;
                  const path = typeof item === 'string' ? item : item.path;
                  if (isFile) {
                    return (
                      <FilePreview
                        key={path}
                        path={path}
                        onRemove={() => {
                          const newAtPath = atPath.filter((v) => (typeof v === 'string' ? v !== path : v.path !== path));
                          emitter.emit('hivemind.selected.file', newAtPath as any);
                          setAtPath(newAtPath as any);
                        }}
                      />
                    );
                  }
                  return null;
                })}
              </HorizontalFileList>
            )}
            {/* Folder tags below */}
            {atPath.some((item) => (typeof item === 'string' ? false : !item.isFile)) && (
              <div className='flex flex-wrap items-center gap-8px mb-8px'>
                {atPath.map((item) => {
                  if (typeof item === 'string') return null;
                  if (!item.isFile) {
                    return (
                      <Badge key={item.path} variant='secondary' className='gap-1 pr-1'>
                        {item.name}
                        <button
                          onClick={() => {
                            const newAtPath = atPath.filter((v) => (typeof v === 'string' ? true : v.path !== item.path));
                            emitter.emit('hivemind.selected.file', newAtPath as any);
                            setAtPath(newAtPath as any);
                          }}
                          className='ml-1 rounded-full hover:bg-muted p-0.5'
                        >
                          <X size={12} />
                        </button>
                      </Badge>
                    );
                  }
                  return null;
                })}
              </div>
            )}
          </>
        }
        onSend={onSendHandler}
      ></SendBox>
    </div>
  );
};

export default HivemindSendBox;
