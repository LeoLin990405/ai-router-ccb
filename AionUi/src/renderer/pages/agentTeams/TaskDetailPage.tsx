/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, Descriptions, Message, Space, Spin, Tag } from '@arco-design/web-react';
import type { IAgentTask } from '@/common/ipcBridge';
import { agentTeamsApi } from './api';

const statusColor: Record<IAgentTask['status'], string> = {
  pending: 'orange',
  in_progress: 'arcoblue',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
};

const TaskDetailPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const [loading, setLoading] = useState(true);
  const [task, setTask] = useState<IAgentTask | null>(null);
  const [dependencies, setDependencies] = useState<{ blocks: string[]; blocked_by: string[] }>({ blocks: [], blocked_by: [] });

  const dependencySummary = useMemo(() => {
    return {
      blockedBy: dependencies.blocked_by.length > 0 ? dependencies.blocked_by.join(', ') : '-',
      blocks: dependencies.blocks.length > 0 ? dependencies.blocks.join(', ') : '-',
    };
  }, [dependencies]);

  const refresh = async () => {
    if (!taskId) {
      return;
    }

    setLoading(true);
    try {
      const [nextTask, nextDependencies] = await Promise.all([agentTeamsApi.getTask(taskId), agentTeamsApi.getTaskDependencies(taskId)]);
      setTask(nextTask);
      setDependencies(nextDependencies);
    } catch (error) {
      Message.error(error instanceof Error ? error.message : String(error));
      setTask(null);
    } finally {
      setLoading(false);
    }
  };

  const transition = async (status: IAgentTask['status']) => {
    if (!task) {
      return;
    }

    try {
      const next = await agentTeamsApi.updateTask(task.id, { status });
      setTask(next);
      Message.success(`Task moved to ${status}`);
    } catch (error) {
      Message.error(error instanceof Error ? error.message : String(error));
    }
  };

  useEffect(() => {
    void refresh();
  }, [taskId]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 0' }}>
        <Spin />
      </div>
    );
  }

  if (!task) {
    return <Card>Task not found.</Card>;
  }

  return (
    <Card title={task.subject}>
      <Descriptions
        column={2}
        data={[
          { label: 'Task ID', value: task.id },
          { label: 'Team ID', value: task.team_id },
          {
            label: 'Status',
            value: <Tag color={statusColor[task.status]}>{task.status}</Tag>,
          },
          { label: 'Priority', value: task.priority },
          { label: 'Assigned To', value: task.assigned_to || '-' },
          { label: 'Provider / Model', value: `${task.provider || '-'} / ${task.model || '-'}` },
          { label: 'Created', value: new Date(task.created_at).toLocaleString() },
          { label: 'Updated', value: new Date(task.updated_at).toLocaleString() },
          { label: 'Started', value: task.started_at ? new Date(task.started_at).toLocaleString() : '-' },
          { label: 'Completed', value: task.completed_at ? new Date(task.completed_at).toLocaleString() : '-' },
          { label: 'Depends On', value: dependencySummary.blockedBy },
          { label: 'Blocks', value: dependencySummary.blocks },
          { label: 'Cost (USD)', value: task.cost_usd.toFixed(4) },
          { label: 'Description', value: task.description },
          { label: 'Result', value: task.result || '-' },
          { label: 'Error', value: task.error || '-' },
        ]}
      />

      <Space style={{ marginTop: 16 }}>
        <Button onClick={() => void refresh()}>Refresh</Button>
        <Button onClick={() => void transition('pending')}>Set Pending</Button>
        <Button onClick={() => void transition('in_progress')}>Set In Progress</Button>
        <Button
          status='success'
          onClick={async () => {
            const result = await agentTeamsApi.runTask(task.id);
            if (result.success) {
              Message.success(`Task executed in ${result.attempts} attempt(s)`);
            } else {
              Message.error(result.error || 'Task execution failed');
            }
            await refresh();
          }}
        >
          Run Task
        </Button>
        <Button status='danger' onClick={() => void transition('failed')}>
          Fail
        </Button>
      </Space>
    </Card>
  );
};

export default TaskDetailPage;
