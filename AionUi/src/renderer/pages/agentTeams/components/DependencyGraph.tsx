/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo } from 'react';
import { Badge } from '@/renderer/components/ui/badge';
import { motion } from 'framer-motion';
import type { IAgentTask } from '@/common/ipcBridge';
import { Typography } from '@/renderer/components/atoms/Typography';

const statusVariant: Record<IAgentTask['status'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
  pending: 'secondary',
  in_progress: 'default',
  completed: 'default',
  failed: 'destructive',
  cancelled: 'outline',
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
        <div className="text-muted-foreground">No tasks yet</div>
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
            <div className="flex flex-col w-full gap-2">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <Typography variant="body2" bold>{task.subject}</Typography>
                  <Badge variant={statusVariant[task.status]}>{task.status}</Badge>
                  {task.status === 'pending' && (
                    <Badge variant={isReady ? 'default' : 'secondary'}>
                      {isReady ? 'READY' : 'BLOCKED'}
                    </Badge>
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
                        <Badge key={dep.id} variant="outline">
                          {dep.subject}
                        </Badge>
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
                        <Badge key={dep.id} variant="outline">
                          {dep.subject}
                        </Badge>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default DependencyGraph;
