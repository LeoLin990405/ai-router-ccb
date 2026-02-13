import React from 'react';
import { Button, Descriptions, Tag, Form, Input } from '@arco-design/web-react';
import { Typography } from '@/renderer/components/atoms/Typography';
import type { IAgentTeam, IAgentTeamStats } from '@/common/ipcBridge';

interface OverviewTabProps {
  team: IAgentTeam;
  stats: IAgentTeamStats | null;
  onRefresh: () => void;
  onQuickCreateTask: () => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  team,
  stats,
  onRefresh,
  onQuickCreateTask,
}) => {
  return (
    <div style={{ padding: '24px 0' }}>
      <Descriptions
        column={2}
        data={[
          { label: <Typography variant="caption" color="secondary">Team ID</Typography>, value: <code style={{ fontSize: '12px' }}>{team.id}</code> },
          { label: <Typography variant="caption" color="secondary">Max Teammates</Typography>, value: team.max_teammates },
          { label: <Typography variant="caption" color="secondary">Strategy</Typography>, value: <Tag style={{ borderRadius: 'var(--radius-sm)' }}>{team.task_allocation_strategy}</Tag> },
          { label: <Typography variant="caption" color="secondary">Total Cost</Typography>, value: <Typography color="warning" bold>${team.total_cost_usd.toFixed(4)}</Typography> },
          { label: <Typography variant="caption" color="secondary">Tasks</Typography>, value: `${stats?.total_tasks || 0} (done ${stats?.completed_tasks || 0}, failed ${stats?.failed_tasks || 0})` },
          { label: <Typography variant="caption" color="secondary">Average Duration</Typography>, value: `${stats?.avg_task_duration_ms || 0} ms` },
        ]}
      />

      <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
        <Button onClick={onRefresh} style={{ borderRadius: 'var(--radius-md)' }}>Refresh Data</Button>
        <Button
          onClick={onQuickCreateTask}
          style={{ borderRadius: 'var(--radius-md)' }}
        >
          Quick Add Task
        </Button>
      </div>
    </div>
  );
};
