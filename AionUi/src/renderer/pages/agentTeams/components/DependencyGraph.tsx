/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo } from 'react';
import { Card, Empty, Space, Tag } from '@arco-design/web-react';
import { motion } from 'framer-motion';
import type { IAgentTask } from '@/common/ipcBridge';
import { Typography } from '@/renderer/components/atoms/Typography';

const statusColor: Record<IAgentTask['status'], string> = {
  pending: 'orange',
  in_progress: 'arcoblue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};

interface DependencyGraphProps {
  tasks: IAgentTask[];
}

const DependencyGraph: React.FC<DependencyGraphProps> = ({ tasks }) => {
  const taskMap = useMemo(() => {
    const map = new Map<string, IAgentTask>();
    for (const task of tasks) {
      map.set(task.id, task);
    }
    return map;
  }, [tasks]);

  const nodeRows = useMemo(() => {
    return tasks.map((task) => {
      const deps = task.blocked_by.map((depId) => taskMap.get(depId)).filter(Boolean) as IAgentTask[];
      const dependents = task.blocks.map((depId) => taskMap.get(depId)).filter(Boolean) as IAgentTask[];
      const isReady = deps.every((dep) => dep.status === 'completed');

      return {
        task,
        deps,
        dependents,
        isReady,
      };
    });
  }, [taskMap, tasks]);

  if (tasks.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Empty description='No tasks yet' />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Typography variant="h6">Dependency Graph</Typography>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {nodeRows.map(({ task, deps, dependents, isReady }) => (
          <motion.div
            key={task.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            style={{
              padding: '16px',
              background: 'var(--bg-1)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            <Space direction='vertical' style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <Typography variant="body2" bold>{task.subject}</Typography>
                  <Tag color={statusColor[task.status]} style={{ borderRadius: 'var(--radius-sm)' }}>{task.status}</Tag>
                  {task.status === 'pending' && (
                    <Tag color={isReady ? 'green' : 'orange'} style={{ borderRadius: 'var(--radius-sm)' }}>
                      {isReady ? 'READY' : 'BLOCKED'}
                    </Tag>
                  )}
                </div>
                <Typography variant="caption" color="tertiary">Priority P{task.priority}</Typography>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '8px' }}>
                <div>
                  <Typography variant="caption" color="secondary" bold style={{ marginBottom: '4px', display: 'block' }}>Depends on:</Typography>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {deps.length === 0 ? (
                      <Typography variant="caption" color="tertiary">None</Typography>
                    ) : (
                      deps.map((dep) => (
                        <Tag key={dep.id} size="small" style={{ borderRadius: 'var(--radius-sm)' }}>
                          {dep.subject}
                        </Tag>
                      ))
                    )}
                  </div>
                </div>

                <div>
                  <Typography variant="caption" color="secondary" bold style={{ marginBottom: '4px', display: 'block' }}>Blocks:</Typography>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {dependents.length === 0 ? (
                      <Typography variant="caption" color="tertiary">None</Typography>
                    ) : (
                      dependents.map((dep) => (
                        <Tag key={dep.id} size="small" style={{ borderRadius: 'var(--radius-sm)' }}>
                          {dep.subject}
                        </Tag>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </Space>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default DependencyGraph;
