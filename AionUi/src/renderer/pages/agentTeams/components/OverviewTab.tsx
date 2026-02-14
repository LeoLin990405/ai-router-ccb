import React from 'react';
import { Button } from '@/renderer/components/ui/button';
import { Badge } from '@/renderer/components/ui/badge';
import { Description } from '@/renderer/components/ui/description';
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
      <Description
        column={2}
        items={[
          { label: <Typography variant="caption" color="secondary">Team ID</Typography>, value: <code style={{ fontSize: '12px' }}>{team.id}</code> },
          { label: <Typography variant="caption" color="secondary">Max Teammates</Typography>, value: team.max_teammates },
          { label: <Typography variant="caption" color="secondary">Strategy</Typography>, value: <Badge variant="outline">{team.task_allocation_strategy}</Badge> },
          { label: <Typography variant="caption" color="secondary">Total Cost</Typography>, value: <Typography color="warning" bold>${team.total_cost_usd.toFixed(4)}</Typography> },
          { label: <Typography variant="caption" color="secondary">Tasks</Typography>, value: `${stats?.total_tasks || 0} (done ${stats?.completed_tasks || 0}, failed ${stats?.failed_tasks || 0})` },
          { label: <Typography variant="caption" color="secondary">Average Duration</Typography>, value: `${stats?.avg_task_duration_ms || 0} ms` },
        ]}
      />

      <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
        <Button onClick={onRefresh} variant="outline">Refresh Data</Button>
        <Button onClick={onQuickCreateTask}>
          Quick Add Task
        </Button>
      </div>
    </div>
  );
};
