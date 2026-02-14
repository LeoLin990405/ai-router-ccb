import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/renderer/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/renderer/components/ui/table';
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
        <Card>
          <CardHeader>
            <CardTitle>
              <Typography variant="h6">Cost Distribution</Typography>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CostChart cost={cost} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>
              <Typography variant="h6">Teammate Performance</Typography>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Teammate</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead>Cost (USD)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(stats?.teammate_stats || []).map((teammate) => (
                  <TableRow key={teammate.teammate_id}>
                    <TableCell>
                      <Typography variant="body2" bold>{teammate.name}</Typography>
                    </TableCell>
                    <TableCell>{teammate.tasks_completed}</TableCell>
                    <TableCell>
                      <Typography color="warning" bold>
                        ${Number(teammate.total_cost_usd || 0).toFixed(4)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
