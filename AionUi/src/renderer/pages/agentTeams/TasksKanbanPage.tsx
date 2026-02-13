/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, InputNumber, Message, Select, Space, Tag } from '@arco-design/web-react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
  DragOverEvent,
  defaultDropAnimationSideEffects,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { motion } from 'framer-motion';
import { ipcBridge } from '@/common';
import type { IAgentTask, IAgentTeam } from '@/common/ipcBridge';
import { agentTeamsApi } from './api';
import { Typography } from '@/renderer/components/atoms/Typography';
import { KanbanColumn } from './components/KanbanColumn';
import { TaskCard } from './components/TaskCard';

const STATUSES: Array<IAgentTask['status']> = ['pending', 'in_progress', 'completed', 'failed', 'cancelled'];

const TasksKanbanPage: React.FC = () => {
  const navigate = useNavigate();
  const [teams, setTeams] = useState<IAgentTeam[]>([]);
  const [teamId, setTeamId] = useState<string>('');
  const [tasks, setTasks] = useState<IAgentTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [form] = Form.useForm();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const refreshTeams = async () => {
    try {
      const nextTeams = await agentTeamsApi.listTeams();
      setTeams(nextTeams);
      if (!teamId && nextTeams[0]) {
        setTeamId(nextTeams[0].id);
      }
    } catch (error) {
      Message.error('Failed to load teams');
    }
  };

  const refreshTasks = async (selectedTeamId: string) => {
    if (!selectedTeamId) {
      setTasks([]);
      return;
    }

    setLoading(true);
    try {
      const nextTasks = await agentTeamsApi.listTasks(selectedTeamId);
      setTasks(nextTasks);
    } catch (error) {
      Message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshTeams();
  }, []);

  useEffect(() => {
    if (teamId) {
      void refreshTasks(teamId);
    }
  }, [teamId]);

  useEffect(() => {
    const unsubscribeTask = ipcBridge.agentTeams.onTaskUpdate.on(({ team_id, task }) => {
      if (!teamId || team_id !== teamId) {
        return;
      }

      setTasks((prev) => {
        const filtered = prev.filter((item) => item.id !== task.id);
        return [task, ...filtered].sort((a, b) => b.priority - a.priority || a.created_at - b.created_at);
      });
    });

    return () => {
      unsubscribeTask();
    };
  }, [teamId]);

  const activeTask = useMemo(() => {
    return tasks.find(t => t.id === activeTaskId);
  }, [tasks, activeTaskId]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveTaskId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    if (activeId === overId) return;

    const isActiveATask = active.data.current?.sortable?.containerId !== undefined || tasks.some(t => t.id === activeId);
    const isOverAColumn = STATUSES.includes(overId as any);

    if (isActiveATask && isOverAColumn) {
      setTasks((prev) => {
        const activeIndex = prev.findIndex((t) => t.id === activeId);
        const task = prev[activeIndex];
        if (task && task.status !== overId) {
          const updatedTask = { ...task, status: overId as IAgentTask['status'] };
          const newTasks = [...prev];
          newTasks[activeIndex] = updatedTask;
          return newTasks;
        }
        return prev;
      });
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveTaskId(null);

    if (!over) return;

    const taskId = active.id as string;
    const overId = over.id as string;
    
    // Determine new status
    let newStatus: IAgentTask['status'] | null = null;
    if (STATUSES.includes(overId as any)) {
      newStatus = overId as IAgentTask['status'];
    } else {
      const overTask = tasks.find(t => t.id === overId);
      if (overTask) {
        newStatus = overTask.status;
      }
    }

    if (!newStatus) return;

    const task = tasks.find(t => t.id === taskId);
    if (task && task.status !== newStatus) {
      try {
        await agentTeamsApi.updateTask(taskId, { status: newStatus });
        // No need to manually refresh, listener will handle it, 
        // but optimistic update already happened in handleDragOver or can be done here.
      } catch (error) {
        Message.error('Failed to update task status');
        void refreshTasks(teamId);
      }
    }
  };

  const createTask = async () => {
    if (!teamId) {
      Message.warning('Please select a team first');
      return;
    }

    try {
      const values = await form.validate();
      await agentTeamsApi.createTask({
        team_id: teamId,
        subject: values.subject,
        description: values.description,
        priority: values.priority,
      });

      form.resetFields();
      Message.success('Task created');
      await refreshTasks(teamId);
    } catch (error) {
      if (error instanceof Error) {
        Message.error(error.message);
      }
    }
  };

  const runTask = async (taskId: string) => {
    try {
      const result = await agentTeamsApi.runTask(taskId);
      if (result.success) {
        Message.success(`Task executed successfully`);
      } else {
        Message.error(result.error || 'Task execution failed');
      }
    } catch (error) {
      Message.error(error instanceof Error ? error.message : String(error));
    } finally {
      void refreshTasks(teamId);
    }
  };

  return (
    <div style={{ padding: '24px', height: '100%', overflowY: 'auto' }}>
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Typography variant="h4" bold>Tasks Kanban</Typography>
          <Typography variant="body2" color="secondary">Drag and drop tasks to manage their workflow</Typography>
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
            <Button 
              onClick={() => void refreshTasks(teamId)} 
              loading={loading}
              style={{ borderRadius: 'var(--radius-sm)' }}
            >
              Refresh
            </Button>
          </Space>
        </Card>
      </div>

      <Card 
        style={{ marginBottom: '24px', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-sm)' }}
        title={<Typography variant="h6">Quick Create Task</Typography>}
      >
        <Form form={form} layout='inline'>
          <Form.Item field='subject' rules={[{ required: true }]}>
            <Input placeholder='Task subject' style={{ width: 240, borderRadius: 'var(--radius-sm)' }} />
          </Form.Item>
          <Form.Item field='description' rules={[{ required: true }]}>
            <Input placeholder='Task description' style={{ width: 380, borderRadius: 'var(--radius-sm)' }} />
          </Form.Item>
          <Form.Item field='priority' initialValue={5}>
            <InputNumber min={1} max={10} style={{ borderRadius: 'var(--radius-sm)' }} />
          </Form.Item>
          <Form.Item>
            <Button type='primary' onClick={() => void createTask()} style={{ borderRadius: 'var(--radius-sm)' }}>
              Create
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div style={{ 
          display: 'flex', 
          gap: '20px', 
          overflowX: 'auto', 
          paddingBottom: '24px',
          minHeight: '600px',
          alignItems: 'flex-start'
        }}>
          {STATUSES.map((status) => (
            <KanbanColumn
              key={status}
              id={status}
              title={status}
              tasks={tasks.filter((t) => t.status === status)}
              onViewDetail={(id) => navigate(`/agent-teams/tasks/${id}`)}
              onRun={runTask}
            />
          ))}
        </div>

        <DragOverlay dropAnimation={{
          sideEffects: defaultDropAnimationSideEffects({
            styles: {
              active: {
                opacity: '0.5',
              },
            },
          }),
        }}>
          {activeTask ? (
            <TaskCard task={activeTask} isDragging />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
};

export default TasksKanbanPage;
