/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import AgentTeamsDashboard from '@/renderer/pages/agentTeams/Dashboard';
import { agentTeamsApi } from '@/renderer/pages/agentTeams/api';

// Mock API
jest.mock('@/renderer/pages/agentTeams/api');

// Mock ipcBridge
jest.mock('@/common', () => ({
  ipcBridge: {
    agentTeams: {
      onTaskUpdate: { on: jest.fn(() => jest.fn()) },
      onMessageReceived: { on: jest.fn(() => jest.fn()) },
      onTeamUpdate: { on: jest.fn(() => jest.fn()) },
    },
  },
}));

// Mock IconParkHOC
jest.mock('@/renderer/components/IconParkHOC', () => {
  return (Component: React.ComponentType) => {
    const MockedIcon = () => <span data-testid="mock-icon">Icon</span>;
    return MockedIcon;
  };
});

describe('Dashboard', () => {
  const mockTeams = [
    {
      id: 'team_1',
      name: '测试团队',
      description: '测试描述',
      status: 'active',
      max_teammates: 5,
      task_allocation_strategy: 'round_robin',
      total_tasks: 10,
      completed_tasks: 5,
      failed_tasks: 1,
      total_cost_usd: 12.34,
      created_at: Date.now(),
      updated_at: Date.now(),
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    (agentTeamsApi.listTeams as jest.Mock).mockResolvedValue(mockTeams);
    (agentTeamsApi.listTasks as jest.Mock).mockResolvedValue([]);
  });

  it('renders dashboard title', async () => {
    render(<AgentTeamsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Agent Teams 仪表盘')).toBeInTheDocument();
    });
  });

  it('renders stats cards', async () => {
    render(<AgentTeamsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('活跃团队')).toBeInTheDocument();
      expect(screen.getByText('总任务数')).toBeInTheDocument();
      expect(screen.getByText('今日完成')).toBeInTheDocument();
      expect(screen.getByText('总成本')).toBeInTheDocument();
    });
  });

  it('displays active team count', async () => {
    render(<AgentTeamsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument(); // 1 个活跃团队
    });
  });

  it('renders trend chart section', async () => {
    render(<AgentTeamsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('任务完成趋势')).toBeInTheDocument();
    });
  });

  it('renders recent activity section', async () => {
    render(<AgentTeamsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Recent Activity')).toBeInTheDocument();
    });
  });

  it('renders active teams section', async () => {
    render(<AgentTeamsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('活跃团队')).toBeInTheDocument();
      expect(screen.getByText('测试团队')).toBeInTheDocument();
    });
  });

  it('calls listTeams on mount', async () => {
    render(<AgentTeamsDashboard />);

    await waitFor(() => {
      expect(agentTeamsApi.listTeams).toHaveBeenCalled();
    });
  });
});
