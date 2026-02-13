/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Card, Space, Table, Tag } from '@arco-design/web-react';
import { motion } from 'framer-motion';
import { ipcBridge } from '@/common';
import type { IAgentTask, IAgentTeamMessage } from '@/common/ipcBridge';
import { Typography } from '@/renderer/components/atoms/Typography';

const MonitorDashboard: React.FC = () => {
  const [recentTasks, setRecentTasks] = useState<IAgentTask[]>([]);
  const [recentMessages, setRecentMessages] = useState<IAgentTeamMessage[]>([]);

  useEffect(() => {
    const unsubscribeTask = ipcBridge.agentTeams.onTaskUpdate.on(({ task }) => {
      setRecentTasks((prev) => [task, ...prev.filter((item) => item.id !== task.id)].slice(0, 30));
    });

    const unsubscribeMessage = ipcBridge.agentTeams.onMessageReceived.on(({ message }) => {
      setRecentMessages((prev) => [message, ...prev].slice(0, 50));
    });

    return () => {
      unsubscribeTask();
      unsubscribeMessage();
    };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{ padding: '24px' }}
    >
      <div style={{ marginBottom: '24px' }}>
        <Typography variant="h4" bold>Real-time Monitor</Typography>
        <Typography variant="body2" color="secondary">Live stream of tasks and messages across all teams</Typography>
      </div>

      <Space direction='vertical' size='large' style={{ width: '100%' }}>
        <Card 
          title={<Typography variant="h6">Task Updates</Typography>}
          style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-sm)' }}
        >
          <Table
            rowKey='id'
            data={recentTasks}
            pagination={{ pageSize: 8 }}
            columns={[
              { 
                title: 'Task', 
                dataIndex: 'subject',
                render: (val) => <Typography variant="body2" bold>{val}</Typography>
              },
              { 
                title: 'Team', 
                dataIndex: 'team_id',
                render: (val) => <code style={{ fontSize: '11px' }}>{val}</code>
              },
              {
                title: 'Status',
                dataIndex: 'status',
                render: (status: IAgentTask['status']) => (
                  <Tag 
                    color={status === 'completed' ? 'green' : status === 'failed' ? 'red' : 'arcoblue'}
                    style={{ borderRadius: 'var(--radius-sm)' }}
                  >
                    {status}
                  </Tag>
                ),
              },
              { title: 'Provider', dataIndex: 'provider' },
              {
                title: 'Updated',
                dataIndex: 'updated_at',
                render: (value: number) => <Typography variant="caption" color="secondary">{new Date(value).toLocaleTimeString()}</Typography>,
              },
            ]}
          />
        </Card>

        <Card 
          title={<Typography variant="h6">Message Stream</Typography>}
          style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-sm)' }}
        >
          <Table
            rowKey='id'
            data={recentMessages}
            pagination={{ pageSize: 10 }}
            columns={[
              { 
                title: 'Type', 
                dataIndex: 'type',
                render: (val: string) => <Tag size="small" style={{ borderRadius: 'var(--radius-sm)' }}>{val.toUpperCase()}</Tag>
              },
              { 
                title: 'Team', 
                dataIndex: 'team_id',
                render: (val) => <code style={{ fontSize: '11px' }}>{val}</code>
              },
              { 
                title: 'Content', 
                dataIndex: 'content',
                render: (val) => <Typography variant="body2" className="line-clamp-1">{val}</Typography>
              },
              {
                title: 'Time',
                dataIndex: 'created_at',
                render: (value: number) => <Typography variant="caption" color="secondary">{new Date(value).toLocaleTimeString()}</Typography>,
              },
            ]}
          />
        </Card>
      </Space>
    </motion.div>
  );
};

export default MonitorDashboard;
