/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/renderer/components/ui/button';
import { Input } from '@/renderer/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/renderer/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/renderer/components/ui/select';
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

  // Quick create form state
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(5);

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
      console.error('Failed to load teams');
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
      console.error(error);
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
        console.error('Failed to update task status');
        void refreshTasks(teamId);
      }
    }
  };

  const createTask = async () => {
    if (!teamId) {
      console.warn('Please select a team first');
      return;
    }

    if (!subject.trim() || !description.trim()) {
      return;
    }

    try {
      await agentTeamsApi.createTask({
        team_id: teamId,
        subject,
        description,
        priority,
      });

      setSubject('');
      setDescription('');
      setPriority(5);
      await refreshTasks(teamId);
    } catch (error) {
      console.error(error);
    }
  };

  const runTask = async (taskId: string) => {
    try {
      const result = await agentTeamsApi.runTask(taskId);
      if (!result.success) {
        console.error(result.error || 'Task execution failed');
      }
    } catch (error) {
      console.error(error);
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
        <Card>
          <CardContent className="py-2 px-4">
            <div className="flex items-center gap-2">
              <Typography variant="body2" bold>Team:</Typography>
              <Select
                value={teamId}
                onValueChange={setTeamId}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {teams.map((team) => (
                    <SelectItem key={team.id} value={team.id}>{team.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button 
                onClick={() => void refreshTasks(teamId)} 
                disabled={loading}
                variant="outline"
              >
                Refresh
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <Typography variant="h6">Quick Create Task</Typography>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <Input
                placeholder="Task subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </div>
            <div className="flex-[2]">
              <Input
                placeholder="Task description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="w-20">
              <Input
                type="number"
                min={1}
                max={10}
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
              />
            </div>
            <Button onClick={() => void createTask()}>
              Create
            </Button>
          </div>
        </CardContent>
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
