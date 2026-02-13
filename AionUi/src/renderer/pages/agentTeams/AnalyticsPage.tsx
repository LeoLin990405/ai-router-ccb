/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Card, Grid, Select, Space, Statistic, Table, Tag } from '@arco-design/web-react';
import { motion } from 'framer-motion';
import type { IAgentCostAnalysis, IAgentTeam, IAgentTeamStats } from '@/common/ipcBridge';
import { agentTeamsApi } from './api';
import { CostChart } from './components';
import { Typography } from '@/renderer/components/atoms/Typography';

const { Row, Col } = Grid;

const AnalyticsPage: React.FC = () => {
  const [teams, setTeams] = useState<IAgentTeam[]>([]);
  const [teamId, setTeamId] = useState<string>('');
  const [stats, setStats] = useState<IAgentTeamStats | null>(null);
  const [cost, setCost] = useState<IAgentCostAnalysis | null>(null);

  const refresh = async (selectedTeamId: string) => {
    if (!selectedTeamId) {
      return;
    }

    const [nextStats, nextCost] = await Promise.all([agentTeamsApi.getTeamStats(selectedTeamId), agentTeamsApi.getCostAnalysis(selectedTeamId)]);
    setStats(nextStats);
    setCost(nextCost);
  };

  useEffect(() => {
    void (async () => {
      const nextTeams = await agentTeamsApi.listTeams();
      setTeams(nextTeams);
      if (nextTeams.length > 0) {
        setTeamId(nextTeams[0].id);
      }
    })();
  }, []);

  useEffect(() => {
    if (teamId) {
      void refresh(teamId);
    }
  }, [teamId]);

  const providerRows = useMemo(() => {
    if (!cost) {
      return [];
    }

    return Object.entries(cost.by_provider).map(([provider, row]) => ({ provider, ...row }));
  }, [cost]);

  const modelRows = useMemo(() => {
    if (!cost) {
      return [];
    }

    return Object.entries(cost.by_model).map(([model, row]) => ({ model, ...row }));
  }, [cost]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ padding: '24px' }}
    >
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Typography variant="h4" bold>Analytics</Typography>
          <Typography variant="body2" color="secondary">Cost and performance analysis for AI teams</Typography>
        </div>
        <Card style={{ borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }} bodyStyle={{ padding: '8px 16px' }}>
          <Space align='center'>
            <Typography variant="body2" bold>Team:</Typography>
            <Select
              style={{ width: 220, borderRadius: 'var(--radius-sm)' }}
              value={teamId}
              onChange={(value) => setTeamId(String(value))}
              options={teams.map((team) => ({ label: team.name, value: team.id }))}
            />
          </Space>
        </Card>
      </div>

      <Space direction='vertical' size='large' style={{ width: '100%' }}>
        <Row gutter={16}>
          <Col span={6}>
            <Card style={{ borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)' }}>
              <div><Typography variant="caption" color="secondary">Total Tasks</Typography><Typography variant="h4" bold>{stats?.total_tasks || 0}</Typography></div>
            </Card>
          </Col>
          <Col span={6}>
            <Card style={{ borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)' }}>
              <div><Typography variant="caption" color="secondary">Completed</Typography><Typography variant="h4" bold style={{ color: 'var(--color-success)' }}>{stats?.completed_tasks || 0}</Typography></div>
            </Card>
          </Col>
          <Col span={6}>
            <Card style={{ borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)' }}>
              <div><Typography variant="caption" color="secondary">Failed</Typography><Typography variant="h4" bold style={{ color: 'var(--color-error)' }}>{stats?.failed_tasks || 0}</Typography></div>
            </Card>
          </Col>
          <Col span={6}>
            <Card style={{ borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)' }}>
              <div><Typography variant="caption" color="secondary">Total Cost (USD)</Typography><Typography variant="h4" bold style={{ color: 'var(--color-warning)' }}>{(cost?.total_cost_usd || 0).toFixed(4)}</Typography></div>
            </Card>
          </Col>
        </Row>

        <Card 
          title={<Typography variant="h6">Cost by Provider (Chart)</Typography>}
          style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-md)' }}
        >
          <CostChart cost={cost} />
        </Card>

        <Card 
          title={<Typography variant="h6">Cost by Provider</Typography>}
          style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-md)' }}
        >
          <Table
            rowKey='provider'
            data={providerRows}
            pagination={false}
            columns={[
              { title: 'Provider', dataIndex: 'provider', render: (value: string) => <Tag color='arcoblue' style={{ borderRadius: 'var(--radius-sm)' }}>{value}</Tag> },
              { title: 'Tasks', dataIndex: 'tasks_count' },
              { title: 'Input Tokens', dataIndex: 'input_tokens' },
              { title: 'Output Tokens', dataIndex: 'output_tokens' },
              { title: 'Cost (USD)', dataIndex: 'cost_usd', render: (value: number) => <Typography color="warning" bold>${value.toFixed(4)}</Typography> },
            ]}
          />
        </Card>

        <Card 
          title={<Typography variant="h6">Cost by Model</Typography>}
          style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-md)' }}
        >
          <Table
            rowKey='model'
            data={modelRows}
            pagination={false}
            columns={[
              { title: 'Model', dataIndex: 'model', render: (value: string) => <Tag style={{ borderRadius: 'var(--radius-sm)' }}>{value}</Tag> },
              { title: 'Tasks', dataIndex: 'tasks_count' },
              { title: 'Input Tokens', dataIndex: 'input_tokens' },
              { title: 'Output Tokens', dataIndex: 'output_tokens' },
              { title: 'Cost (USD)', dataIndex: 'cost_usd', render: (value: number) => <Typography color="warning" bold>${value.toFixed(4)}</Typography> },
            ]}
          />
        </Card>
      </Space>
    </motion.div>
  );
};

export default AnalyticsPage;
