/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Message, Select, Space, Switch, Tag, Typography } from '@arco-design/web-react';
import { ConfigStorage } from '@/common/storage';
import { DEFAULT_HIVEMIND_CONFIG, HIVEMIND_PROVIDER_OPTIONS, type HivemindConfig } from '@/agent/hivemind/types';
import { useHivemindStatus } from '@/renderer/hooks/useHivemindStatus';
import RateLimitControl from './RateLimitControl';
import { useTranslation } from 'react-i18next';

const HivemindModalContent: React.FC = () => {
  const { t } = useTranslation();
  const [config, setConfig] = useState<HivemindConfig>(DEFAULT_HIVEMIND_CONFIG);
  const { status, connected, error, refresh } = useHivemindStatus(config.gatewayUrl);

  useEffect(() => {
    ConfigStorage.get('hivemind.config')
      .then((saved) => {
        if (!saved) {
          return;
        }
        setConfig((prev) => ({
          ...prev,
          ...saved,
          defaultProvider: saved.defaultProvider ?? null,
          agent: saved.agent ?? null,
        }));
      })
      .catch((err) => {
        console.error('Failed to load hivemind config:', err);
      });
  }, []);

  const enabledProviders = useMemo(() => {
    return (status?.providers || []).filter((provider) => provider.enabled !== false);
  }, [status]);

  const handleSave = async () => {
    try {
      await ConfigStorage.set('hivemind.config', {
        gatewayUrl: config.gatewayUrl,
        defaultProvider: config.defaultProvider,
        timeoutS: config.timeoutS,
        streaming: config.streaming,
        agent: config.agent,
        cacheBypass: config.cacheBypass,
        systemPrompt: config.systemPrompt,
      });
      Message.success(t('hivemind.settings.saveSuccess'));
      void refresh();
    } catch (err) {
      Message.error(err instanceof Error ? err.message : t('hivemind.settings.saveFailed'));
    }
  };

  return (
    <div className='flex flex-col gap-16px'>
      <Typography.Title heading={5} style={{ margin: 0 }}>
        {t('hivemind.settings.title')}
      </Typography.Title>

      <Card>
        <div className='flex items-center justify-between gap-12px flex-wrap'>
          <Space>
            <Tag color={connected ? 'green' : 'red'}>{connected ? t('hivemind.settings.connected') : t('hivemind.settings.disconnected')}</Tag>
            {error && <Typography.Text type='error'>{error}</Typography.Text>}
          </Space>
          <Space>
            <Button size='small' onClick={() => void refresh()}>
              {t('hivemind.settings.refresh')}
            </Button>
            <Button size='small' type='primary' onClick={handleSave}>
              {t('hivemind.settings.save')}
            </Button>
          </Space>
        </div>
        {status?.gateway && (
          <div className='mt-12px text-13px text-t-secondary'>
            {t('hivemind.settings.uptime')}: {Math.floor((status.gateway.uptime_s || 0) / 60)}m · {t('hivemind.settings.requests')}: {status.gateway.total_requests || 0} · {t('hivemind.settings.active')}: {status.gateway.active_requests || 0}
          </div>
        )}
        <div className='mt-8px text-13px text-t-secondary'>
          {t('hivemind.settings.enabledProviders')}: {enabledProviders.length}
        </div>
      </Card>

      <Card>
        <Form layout='vertical'>
          <Form.Item label={t('hivemind.settings.gatewayUrl')}>
            <Input
              value={config.gatewayUrl}
              placeholder={t('hivemind.settings.gatewayUrlPlaceholder')}
              onChange={(value) => {
                setConfig((prev) => ({ ...prev, gatewayUrl: value }));
              }}
            />
          </Form.Item>

          <Form.Item label={t('hivemind.settings.defaultProvider')}>
            <Select
              value={config.defaultProvider ?? ''}
              options={HIVEMIND_PROVIDER_OPTIONS}
              allowClear
              onChange={(value) => {
                const normalized = typeof value === 'string' ? value : '';
                setConfig((prev) => ({
                  ...prev,
                  defaultProvider: normalized || null,
                }));
              }}
            />
          </Form.Item>

          <Form.Item label={t('hivemind.settings.timeout')}>
            <InputNumber
              value={config.timeoutS}
              min={5}
              max={900}
              onChange={(value) => {
                const normalized = typeof value === 'number' && Number.isFinite(value) ? value : DEFAULT_HIVEMIND_CONFIG.timeoutS;
                setConfig((prev) => ({ ...prev, timeoutS: normalized }));
              }}
            />
          </Form.Item>

          <Form.Item label={t('hivemind.settings.agentRole')}>
            <Input
              value={config.agent || ''}
              placeholder={t('hivemind.settings.agentRolePlaceholder')}
              onChange={(value) => {
                setConfig((prev) => ({
                  ...prev,
                  agent: value.trim() ? value.trim() : null,
                }));
              }}
            />
          </Form.Item>

          <Form.Item label={t('hivemind.settings.systemPrompt')}>
            <Input.TextArea
              value={config.systemPrompt || ''}
              placeholder={t('hivemind.settings.systemPromptPlaceholder')}
              autoSize={{ minRows: 2, maxRows: 6 }}
              onChange={(value) => {
                setConfig((prev) => ({
                  ...prev,
                  systemPrompt: value.trim() ? value.trim() : null,
                }));
              }}
            />
          </Form.Item>

          <Form.Item label={t('hivemind.settings.streaming')}>
            <Switch
              checked={config.streaming}
              onChange={(checked) => {
                setConfig((prev) => ({ ...prev, streaming: checked }));
              }}
            />
          </Form.Item>

          <Form.Item label={t('hivemind.settings.cacheBypass')}>
            <Switch
              checked={config.cacheBypass}
              onChange={(checked) => {
                setConfig((prev) => ({ ...prev, cacheBypass: checked }));
              }}
            />
          </Form.Item>
        </Form>
      </Card>

      {enabledProviders.length > 0 && (
        <Card>
          <Typography.Title heading={6} style={{ margin: '0 0 12px 0' }}>
            {t('hivemind.settings.providerStatus')}
          </Typography.Title>
          <div className='flex flex-col gap-8px'>
            {enabledProviders.map((provider) => {
              const statusText = provider.status || 'unknown';
              const statusColor = statusText === 'healthy' || statusText === 'ok' ? '#00b42a' : statusText === 'degraded' ? '#ff7d00' : '#f53f3f';
              return (
                <div key={provider.name} className='flex items-center justify-between text-13px'>
                  <Space>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: statusColor,
                        display: 'inline-block',
                      }}
                    />
                    <Typography.Text bold>{provider.name}</Typography.Text>
                    <Tag size='small' color={statusText === 'healthy' || statusText === 'ok' ? 'green' : statusText === 'degraded' ? 'orange' : 'red'}>
                      {statusText}
                    </Tag>
                  </Space>
                  <Space className='text-t-secondary'>
                    {typeof provider.avg_latency_ms === 'number' && <span>{(provider.avg_latency_ms / 1000).toFixed(1)}s</span>}
                    {typeof provider.success_rate === 'number' && <span>{(provider.success_rate * 100).toFixed(0)}%</span>}
                    {typeof provider.total_requests === 'number' && <span>{provider.total_requests} req</span>}
                  </Space>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <Card>
        <Typography.Title heading={6} style={{ margin: '0 0 12px 0' }}>
          {t('hivemind.settings.rateLimit', { defaultValue: 'Rate Limiting' })}
        </Typography.Title>
        <RateLimitControl gatewayUrl={config.gatewayUrl} />
      </Card>
    </div>
  );
};

export default HivemindModalContent;
