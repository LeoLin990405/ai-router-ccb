/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Tag } from '@arco-design/web-react';
import { PROVIDER_TIERS } from '@/agent/hivemind/types';

interface HivemindProviderBadgeProps {
  provider: string;
  cached?: boolean;
  latencyMs?: number | null;
  totalTokens?: number | null;
}

const HivemindProviderBadge: React.FC<HivemindProviderBadgeProps> = ({ provider, cached = false, latencyMs, totalTokens }) => {
  const { t } = useTranslation();
  const tier = PROVIDER_TIERS[provider] || { emoji: '🤖', label: 'Unknown', color: 'gray' };

  return (
    <div className='flex items-center gap-6px mb-6px'>
      <Tag color={tier.color} size='small'>
        {tier.emoji} {provider}
      </Tag>
      <Tag size='small'>{tier.label}</Tag>
      {cached && (
        <Tag color='green' size='small'>
          {t('hivemind.cached')}
        </Tag>
      )}
      {typeof latencyMs === 'number' && Number.isFinite(latencyMs) && (
        <Tag size='small'>{(latencyMs / 1000).toFixed(1)}s</Tag>
      )}
      {typeof totalTokens === 'number' && totalTokens > 0 && (
        <Tag size='small'>⚡ {t('hivemind.tokens', { count: totalTokens })}</Tag>
      )}
    </div>
  );
};

export default HivemindProviderBadge;
