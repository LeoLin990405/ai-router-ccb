/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ipcBridge } from '@/common';
import { HIVEMIND_PROVIDER_OPTIONS, PROVIDER_TIERS } from '@/agent/hivemind/types';
import { useHivemindStatus } from '@/renderer/hooks/useHivemindStatus';
import { Alert, Tag } from '@arco-design/web-react';
import { Badge } from '@/renderer/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/renderer/components/ui/select';
import SendBox from '@/renderer/components/sendbox';
import { Typography } from '@/renderer/components/atoms/Typography';
import { tokens } from '@/renderer/design-tokens';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  provider?: string | null;
  cached?: boolean;
  latencyMs?: number | null;
  timestamp: number;
}

const AGENT_TEAMS_CHAT_INITIAL_MESSAGE_KEY = 'agent_teams_chat_initial_message';
const AUTO_PROVIDER_VALUE = '__auto_provider__';

/**
 * Standalone Chat page under Agent Teams — replaces the old HiveMind conversation entry.
 * Supports all Gateway providers and @fast/@all parallel queries.
 */
const ChatPage: React.FC = () => {
  const { t } = useTranslation();
  const { connected, reconnecting, providers } = useHivemindStatus();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [lastProvider, setLastProvider] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastProviderRef = useRef<string | null>(null);

  // Keep ref in sync
  useEffect(() => {
    lastProviderRef.current = lastProvider;
  }, [lastProvider]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  const chatTeamId = '__standalone_chat__';

  // Listen for response stream
  useEffect(() => {
    return ipcBridge.agentTeams.teamChat.responseStream.on((event) => {
      if (event.team_id !== chatTeamId) return;

      switch (event.type) {
        case 'start':
          setStreaming(true);
          setStreamingContent('');
          setLastProvider(null);
          break;
        case 'text':
          setStreamingContent((prev) => prev + (typeof event.data === 'string' ? event.data : ''));
          break;
        case 'agent_status': {
          const status = event.data as { backend?: string; cached?: boolean; latencyMs?: number | null };
          if (status.backend) setLastProvider(status.backend);
          break;
        }
        case 'finish':
          setStreaming(false);
          setStreamingContent((prev) => {
            if (prev.trim()) {
              setMessages((msgs) => [
                ...msgs,
                {
                  id: event.msg_id || `msg-${Date.now()}`,
                  role: 'assistant',
                  content: prev,
                  provider: lastProviderRef.current,
                  timestamp: Date.now(),
                },
              ]);
            }
            return '';
          });
          break;
        case 'error':
          setStreaming(false);
          setStreamingContent('');
          setMessages((msgs) => [
            ...msgs,
            {
              id: `err-${Date.now()}`,
              role: 'assistant',
              content: `Error: ${typeof event.data === 'string' ? event.data : 'Unknown error'}`,
              timestamp: Date.now(),
            },
          ]);
          break;
      }
    });
  }, [chatTeamId]);

  const handleSend = useCallback(
    async (message: string) => {
      if (!message.trim() || streaming) return;

      setMessages((prev) => [...prev, { id: `user-${Date.now()}`, role: 'user', content: message, timestamp: Date.now() }]);
      setContent('');

      try {
        await ipcBridge.agentTeams.teamChat.send.invoke({
          team_id: chatTeamId,
          message,
          provider: selectedProvider,
          model: null,
        });
      } catch (error) {
        console.error('[ChatPage] Failed to send:', error);
      }
    },
    [chatTeamId, selectedProvider, streaming]
  );

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(AGENT_TEAMS_CHAT_INITIAL_MESSAGE_KEY);
      if (!stored) return;
      sessionStorage.removeItem(AGENT_TEAMS_CHAT_INITIAL_MESSAGE_KEY);
      const parsed = JSON.parse(stored) as { input?: string };
      if (parsed?.input?.trim()) {
        void handleSend(parsed.input);
      }
    } catch (error) {
      console.error('[ChatPage] Failed to process initial message:', error);
    }
  }, [handleSend]);

  const getProviderHealthColor = useCallback(
    (providerValue: string): string | null => {
      if (!providerValue || providerValue.startsWith('@')) return null;
      const ps = providers.find((p) => p.name === providerValue);
      if (!ps) return null;
      if (ps.status === 'healthy' || ps.status === 'ok') return '#00b42a';
      if (ps.status === 'degraded') return '#ff7d00';
      return '#f53f3f';
    },
    [providers]
  );

  return (
    <div className='hive-agent-page h-full flex flex-col'>
      {!connected && <Alert className='mx-4 mt-2 shrink-0' type='warning' content={reconnecting ? t('hivemind.status.reconnecting') : t('hivemind.status.reconnectFailed')} showIcon closable />}

      {/* Messages area */}
      <div ref={scrollRef} className='flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-3'>
        {messages.length === 0 && !streaming && (
          <div className='flex flex-col items-center justify-center h-full gap-3'>
            <Typography variant='h5' color='secondary'>
              {t('agentTeams.chatWelcome', { defaultValue: 'Agent Teams Chat' })}
            </Typography>
            <Typography variant='body2' color='secondary'>
              {t('agentTeams.chatWelcomeDesc', { defaultValue: 'Chat with any AI provider through the Gateway. Select a provider or let smart routing decide.' })}
            </Typography>
            {/* Provider speed tiers */}
            <div className='flex flex-wrap gap-2 mt-2'>
              {Object.entries(PROVIDER_TIERS)
                .filter(([key]) => !key.startsWith('@'))
                .map(([name, tier]) => (
                  <Tag key={name} color={tier.color} size='small'>
                    {tier.emoji} {name} — {tier.label}
                  </Tag>
                ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg px-3 py-2 ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              <Typography variant='body2' className='whitespace-pre-wrap break-words'>
                {msg.content}
              </Typography>
              {msg.provider && (
                <div className='mt-1'>
                  <Tag size='small' color={PROVIDER_TIERS[msg.provider]?.color ?? 'gray'}>
                    {PROVIDER_TIERS[msg.provider]?.emoji ?? '🤖'} {msg.provider}
                  </Tag>
                </div>
              )}
            </div>
          </div>
        ))}

        {streaming && (
          <div className='flex justify-start'>
            <div className='max-w-[80%] rounded-lg px-3 py-2 bg-muted'>
              <Typography variant='body2' className='whitespace-pre-wrap break-words'>
                {streamingContent || '...'}
              </Typography>
              {lastProvider && (
                <Badge variant='outline' className='mt-1 text-xs'>
                  {PROVIDER_TIERS[lastProvider]?.emoji ?? '🤖'} {lastProvider}
                </Badge>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Send area */}
      <div className='shrink-0 px-6 pb-4 pt-2 border-t'>
        <div className='max-w-800px mx-auto'>
          <SendBox
            value={content}
            onChange={setContent}
            loading={streaming}
            disabled={!connected || streaming}
            placeholder={streaming ? t('hivemind.processing') : t('agentTeams.chatPlaceholder', { defaultValue: 'Chat with your team...' })}
            defaultMultiLine
            lockMultiLine
            sendButtonPrefix={
              <>
                {/* Provider selector */}
                <Select value={selectedProvider ?? AUTO_PROVIDER_VALUE} onValueChange={(v: string) => setSelectedProvider(v === AUTO_PROVIDER_VALUE ? null : v)} disabled={streaming}>
                  <SelectTrigger className='w-[180px] h-7 text-xs' style={{ borderRadius: tokens.radius.md }}>
                    <SelectValue placeholder={t('hivemind.selectProvider')}>
                      {(() => {
                        const opt = HIVEMIND_PROVIDER_OPTIONS.find((o) => o.value === (selectedProvider ?? ''));
                        const label = opt?.label ?? selectedProvider ?? '🧠 Auto';
                        const hc = getProviderHealthColor(selectedProvider ?? '');
                        return (
                          <span className='flex items-center gap-1'>
                            {hc && <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: hc, display: 'inline-block', flexShrink: 0 }} />}
                            {label}
                          </span>
                        );
                      })()}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {HIVEMIND_PROVIDER_OPTIONS.map((opt) => {
                      const optionValue = opt.value === '' ? AUTO_PROVIDER_VALUE : opt.value;
                      const hc = getProviderHealthColor(opt.value);
                      return (
                        <SelectItem key={optionValue} value={optionValue} className='text-xs'>
                          <span className='flex items-center gap-1'>
                            {hc && <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: hc, display: 'inline-block', flexShrink: 0 }} />}
                            {opt.label}
                          </span>
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              </>
            }
            onSend={handleSend}
          />
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
