import React from 'react';
import { Badge } from '@/renderer/components/ui/badge';
import { motion } from 'framer-motion';
import { Typography } from '@/renderer/components/atoms/Typography';
import DependencyGraph from './DependencyGraph';
import type { IAgentTask } from '@/common/ipcBridge';

interface TasksTabProps {
  tasks: IAgentTask[];
}

export const TasksTab: React.FC<TasksTabProps> = ({ tasks }) => {
  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'completed': return 'default';
      case 'failed': return 'destructive';
      default: return 'secondary';
    }
  };

  return (
    <div style={{ padding: '24px 0' }}>
      <DependencyGraph tasks={tasks} />
      <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {tasks.map((task) => (
          <motion.div
            key={task.id}
            layout
            style={{
              padding: 16,
              background: 'var(--bg-1)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              <Typography variant="body1" bold>{task.subject}</Typography>
              <Typography variant="caption" color="secondary">{task.description}</Typography>
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <Typography variant="caption" color="secondary">P{task.priority}</Typography>
              <Badge variant={getStatusVariant(task.status)}>
                {task.status}
              </Badge>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};
