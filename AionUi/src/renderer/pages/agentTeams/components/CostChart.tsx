/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo } from 'react';
import { Card, Empty, Space, Tag } from '@arco-design/web-react';
import { motion } from 'framer-motion';
import type { IAgentCostAnalysis } from '@/common/ipcBridge';
import { Typography } from '@/renderer/components/atoms/Typography';

interface CostChartProps {
  cost: IAgentCostAnalysis | null;
  title?: string;
}

const CostChart: React.FC<CostChartProps> = ({ cost, title }) => {
  const rows = useMemo(() => {
    if (!cost) {
      return [];
    }

    return Object.entries(cost.by_provider)
      .map(([provider, row]) => ({ provider, ...row }))
      .sort((a, b) => b.cost_usd - a.cost_usd);
  }, [cost]);

  const maxValue = useMemo(() => rows.reduce((acc, row) => Math.max(acc, row.cost_usd), 0), [rows]);

  if (!cost || rows.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Empty description='No cost data yet' />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {title && <Typography variant="h6">{title}</Typography>}
      <Space direction='vertical' size={20} style={{ width: '100%' }}>
        {rows.map((row) => {
          const width = maxValue > 0 ? Math.max(6, (row.cost_usd / maxValue) * 100) : 0;
          return (
            <div key={row.provider} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <Tag color='arcoblue' style={{ borderRadius: 'var(--radius-sm)' }}>{row.provider}</Tag>
                  <Typography variant="body2" bold>${row.cost_usd.toFixed(4)}</Typography>
                </div>
                <Typography variant="caption" color="secondary">
                  {row.tasks_count} tasks • {row.input_tokens + row.output_tokens} tokens
                </Typography>
              </div>
              <div
                style={{
                  height: 10,
                  width: '100%',
                  background: 'var(--bg-2)',
                  borderRadius: 'var(--radius-full)',
                  overflow: 'hidden',
                }}
              >
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${width}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                  style={{
                    height: '100%',
                    background: 'var(--color-primary)',
                    boxShadow: '0 0 8px var(--primary-rgba-40)'
                  }}
                />
              </div>
            </div>
          );
        })}
      </Space>
    </div>
  );
};

export default CostChart;
