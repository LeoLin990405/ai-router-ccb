/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { ipcBridge } from '@/common';
import type { IAgentCostAnalysis, IAgentTask, IAgentTeam, IAgentTeamMessage, IAgentTeamStats, IAgentTeammate } from '@/common/ipcBridge';

const ensureSuccess = <T>(response: { success: boolean; data?: T; msg?: string }, fallbackMessage: string): T => {
  if (!response.success || response.data === undefined) {
    throw new Error(response.msg || fallbackMessage);
  }
  return response.data;
};

export const agentTeamsApi = {
  listTeams: async (): Promise<IAgentTeam[]> => {
    const response = await ipcBridge.agentTeams.listTeams.invoke({ limit: 200, offset: 0 });
    return ensureSuccess(response, 'Failed to load teams');
  },

  createTeam: async (payload: { name: string; description?: string; max_teammates?: number; task_allocation_strategy?: 'round_robin' | 'load_balance' | 'skill_based' }): Promise<IAgentTeam> => {
    const response = await ipcBridge.agentTeams.createTeam.invoke(payload);
    return ensureSuccess(response, 'Failed to create team');
  },

  getTeam: async (teamId: string): Promise<IAgentTeam> => {
    const response = await ipcBridge.agentTeams.getTeam.invoke({ team_id: teamId });
    return ensureSuccess(response, 'Failed to load team');
  },

  listTeammates: async (teamId: string): Promise<IAgentTeammate[]> => {
    const response = await ipcBridge.agentTeams.listTeammates.invoke({ team_id: teamId });
    return ensureSuccess(response, 'Failed to load teammates');
  },

  addTeammate: async (payload: {
    team_id: string;
    name: string;
    role: string;
    provider: string;
    model: string;
    skills?: string[];
  }): Promise<IAgentTeammate> => {
    const response = await ipcBridge.agentTeams.addTeammate.invoke(payload);
    return ensureSuccess(response, 'Failed to add teammate');
  },

  getTask: async (taskId: string): Promise<IAgentTask> => {
    const response = await ipcBridge.agentTeams.getTask.invoke({ task_id: taskId });
    return ensureSuccess(response, 'Failed to load task');
  },

  listTasks: async (teamId: string): Promise<IAgentTask[]> => {
    const response = await ipcBridge.agentTeams.listTasks.invoke({ team_id: teamId, limit: 1000, offset: 0 });
    return ensureSuccess(response, 'Failed to load tasks');
  },

  getTaskDependencies: async (taskId: string): Promise<{ blocks: string[]; blocked_by: string[] }> => {
    const response = await ipcBridge.agentTeams.getTaskDependencies.invoke({ task_id: taskId });
    return ensureSuccess(response, 'Failed to load task dependencies');
  },

  createTask: async (payload: {
    team_id: string;
    subject: string;
    description: string;
    priority?: number;
    blocked_by?: string[];
    metadata?: Record<string, unknown>;
  }): Promise<IAgentTask> => {
    const response = await ipcBridge.agentTeams.createTask.invoke(payload);
    return ensureSuccess(response, 'Failed to create task');
  },

  updateTask: async (taskId: string, updates: Partial<IAgentTask>): Promise<IAgentTask> => {
    const response = await ipcBridge.agentTeams.updateTask.invoke({ task_id: taskId, updates });
    return ensureSuccess(response, 'Failed to update task');
  },

  getMessages: async (teamId: string): Promise<IAgentTeamMessage[]> => {
    const response = await ipcBridge.agentTeams.getMessages.invoke({ team_id: teamId, limit: 200, offset: 0 });
    return ensureSuccess(response, 'Failed to load messages');
  },

  sendMessage: async (payload: {
    team_id: string;
    type: 'broadcast' | 'p2p' | 'status_update' | 'system';
    content: string;
    from_teammate_id?: string;
    to_teammate_id?: string;
  }): Promise<IAgentTeamMessage> => {
    const response = await ipcBridge.agentTeams.sendMessage.invoke(payload);
    return ensureSuccess(response, 'Failed to send message');
  },

  getTeamStats: async (teamId: string): Promise<IAgentTeamStats> => {
    const response = await ipcBridge.agentTeams.getTeamStats.invoke({ team_id: teamId });
    return ensureSuccess(response, 'Failed to load team stats');
  },

  getCostAnalysis: async (teamId: string): Promise<IAgentCostAnalysis> => {
    const response = await ipcBridge.agentTeams.getCostAnalysis.invoke({ team_id: teamId });
    return ensureSuccess(response, 'Failed to load cost analysis');
  },

  runTask: async (taskId: string): Promise<{ success: boolean; task_id: string; attempts: number; provider?: string; model?: string; error?: string }> => {
    const response = await ipcBridge.agentTeams.runTask.invoke({ task_id: taskId });
    return ensureSuccess(response, 'Failed to run task');
  },

  runTeam: async (teamId: string): Promise<{ team_id: string; scheduled: number; started: number; completed: number; failed: number }> => {
    const response = await ipcBridge.agentTeams.runTeam.invoke({ team_id: teamId });
    return ensureSuccess(response, 'Failed to run team');
  },
};
