/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskCard } from '@/renderer/pages/agentTeams/components/TaskCard';
import type { IAgentTask } from '@/common/ipcBridge';

// Mock @dnd-kit
jest.mock('@dnd-kit/sortable', () => ({
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: jest.fn(),
    transform: null,
    transition: undefined,
    isDragging: false,
  }),
}));

describe('TaskCard', () => {
  const mockTask: IAgentTask = {
    id: 'task_1',
    team_id: 'team_1',
    subject: '测试任务',
    description: '这是一个测试任务描述',
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
  };

  it('renders task title and description', () => {
    render(<TaskCard task={mockTask} />);

    expect(screen.getByText('测试任务')).toBeInTheDocument();
    expect(screen.getByText(/这是一个测试任务描述/)).toBeInTheDocument();
  });

  it('shows priority badge', () => {
    render(<TaskCard task={mockTask} />);

    expect(screen.getByText(/P5/)).toBeInTheDocument();
  });

  it('shows high priority color for priority >= 8', () => {
    const highPriorityTask = { ...mockTask, priority: 9 };
    render(<TaskCard task={highPriorityTask} />);

    expect(screen.getByText(/P9/)).toBeInTheDocument();
  });

  it('shows dependencies indicator when blocked', () => {
    const blockedTask = { ...mockTask, blocked_by: ['task_2', 'task_3'] };
    render(<TaskCard task={blockedTask} />);

    expect(screen.getByText(/依赖 2 个任务/)).toBeInTheDocument();
  });

  it('shows provider when assigned', () => {
    const assignedTask = { ...mockTask, provider: 'claude' };
    render(<TaskCard task={assignedTask} />);

    expect(screen.getByText('claude')).toBeInTheDocument();
  });

  it('calls onViewDetail when title is clicked', () => {
    const onViewDetail = jest.fn();
    render(<TaskCard task={mockTask} onViewDetail={onViewDetail} />);

    const titleButton = screen.getByText('测试任务');
    fireEvent.click(titleButton);

    expect(onViewDetail).toHaveBeenCalledWith('task_1');
  });

  it('shows cost when cost_usd > 0', () => {
    const costlyTask = { ...mockTask, cost_usd: 0.1234 };
    render(<TaskCard task={costlyTask} />);

    expect(screen.getByText(/\$0\.12/)).toBeInTheDocument();
  });

  it('shows completed status indicator for completed tasks', () => {
    const completedTask = { ...mockTask, status: 'completed' };
    render(<TaskCard task={completedTask} />);

    expect(screen.getByText(/已完成/)).toBeInTheDocument();
  });

  it('shows failed status indicator for failed tasks', () => {
    const failedTask = { ...mockTask, status: 'failed' };
    render(<TaskCard task={failedTask} />);

    expect(screen.getByText(/失败/)).toBeInTheDocument();
  });
});
