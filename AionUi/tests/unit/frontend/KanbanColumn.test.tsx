/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { KanbanColumn } from '@/renderer/pages/agentTeams/components/KanbanColumn';
import type { IAgentTask } from '@/common/ipcBridge';

// Mock @dnd-kit
jest.mock('@dnd-kit/core', () => ({
  useDroppable: () => ({
    setNodeRef: jest.fn(),
    isOver: false,
  }),
}));

jest.mock('@dnd-kit/sortable', () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  verticalListSortingStrategy: {},
}));

describe('KanbanColumn', () => {
  const mockTasks: IAgentTask[] = [
    {
      id: 'task_1',
      team_id: 'team_1',
      subject: '任务 1',
      description: '描述 1',
      status: 'pending',
      priority: 5,
      assigned_to: null,
      provider: null,
      model: null,
      created_at: Date.now(),
      updated_at: Date.now(),
      started_at: null,
      completed_at: null,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      blocks: [],
      blocked_by: [],
      result: null,
      error: null,
      metadata: null,
    },
  ];

  it('renders column title', () => {
    render(<KanbanColumn id="pending" title="pending" tasks={mockTasks} />);

    // pending 状态应该显示为 "待处理"
    expect(screen.getByText('待处理')).toBeInTheDocument();
  });

  it('shows task count', () => {
    render(<KanbanColumn id="pending" title="pending" tasks={mockTasks} />);

    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('shows empty state when no tasks', () => {
    render(<KanbanColumn id="pending" title="pending" tasks={[]} />);

    expect(screen.getByText(/拖拽任务到此处/)).toBeInTheDocument();
  });

  it('renders multiple tasks', () => {
    const multipleTasks = [
      ...mockTasks,
      {
        ...mockTasks[0],
        id: 'task_2',
        subject: '任务 2',
      },
    ];
    render(<KanbanColumn id="pending" title="pending" tasks={multipleTasks} />);

    expect(screen.getByText('任务 1')).toBeInTheDocument();
    expect(screen.getByText('任务 2')).toBeInTheDocument();
  });

  it('renders all status columns correctly', () => {
    const statuses = [
      { id: 'pending', label: '待处理' },
      { id: 'in_progress', label: '进行中' },
      { id: 'completed', label: '已完成' },
      { id: 'failed', label: '失败' },
      { id: 'cancelled', label: '已取消' },
    ];

    statuses.forEach(({ id, label }) => {
      const { unmount } = render(<KanbanColumn id={id} title={id} tasks={[]} />);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    });
  });
});
