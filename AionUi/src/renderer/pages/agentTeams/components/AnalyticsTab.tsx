import React from 'react';
import { Card, Table } from '@arco-design/web-react';
import { Typography } from '@/renderer/components/atoms/Typography';
import CostChart from './CostChart';
import type { IAgentCostAnalysis, IAgentTeamStats } from '@/common/ipcBridge';

interface AnalyticsTabProps {
  stats: IAgentTeamStats | null;
  cost: IAgentCostAnalysis | null;
}

export const AnalyticsTab: React.FC<AnalyticsTabProps> = ({ stats, cost }) => {
  return (
    <div style={{ padding: '24px 0' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <Card 
          title={<Typography variant="h6">Cost Distribution</Typography>} 
          style={{ borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)' }}
        >
          <CostChart cost={cost} />
        </Card>
        <Card 
          title={<Typography variant="h6">Teammate Performance</Typography>} 
          style={{ borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)' }}
        >
          <Table
            rowKey='teammate_id'
            pagination={false}
            data={stats?.teammate_stats || []}
            columns={[
              { title: 'Teammate', dataIndex: 'name', render: (val) => <Typography variant="body2" bold>{val}</Typography> },
              { title: 'Completed', dataIndex: 'tasks_completed' },
              {
                title: 'Cost (USD)',
                dataIndex: 'total_cost_usd',
                render: (value: number) => <Typography color="warning" bold>${Number(value || 0).toFixed(4)}</Typography>,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
};
