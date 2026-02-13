/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useRef, useCallback } from 'react';
import { ipcBridge } from '@/common';
import type { IAgentTask, IAgentTeam, IAgentTeammate, IAgentTeamMessage } from '@/common/ipcBridge';

interface RealtimeUpdateCallbacks {
  onTeamUpdate?: (team: IAgentTeam) => void;
  onTaskUpdate?: (task: IAgentTask) => void;
  onTeammateUpdate?: (teammate: IAgentTeammate) => void;
  onMessageReceived?: (message: IAgentTeamMessage) => void;
}

/**
 * 实时更新 Hook
 * 订阅 Agent Teams 的实时更新事件
 */
export function useRealtimeUpdates(
  teamId: string | null,
  callbacks: RealtimeUpdateCallbacks
) {
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  useEffect(() => {
    if (!teamId) return;

    // 订阅团队更新
    const unsubTeam = ipcBridge.agentTeams.onTeamUpdate.on(({ team_id, team }) => {
      if (team_id === teamId) {
        callbacksRef.current.onTeamUpdate?.(team);
      }
    });

    // 订阅任务更新
    const unsubTask = ipcBridge.agentTeams.onTaskUpdate.on(({ team_id, task }) => {
      if (team_id === teamId) {
        callbacksRef.current.onTaskUpdate?.(task);
      }
    });

    // 订阅成员更新
    const unsubTeammate = ipcBridge.agentTeams.onTeammateUpdate.on(({ team_id, teammate }) => {
      if (team_id === teamId) {
        callbacksRef.current.onTeammateUpdate?.(teammate);
      }
    });

    // 订阅消息接收
    const unsubMessage = ipcBridge.agentTeams.onMessageReceived.on(({ team_id, message }) => {
      if (team_id === teamId) {
        callbacksRef.current.onMessageReceived?.(message);
      }
    });

    return () => {
      unsubTeam();
      unsubTask();
      unsubTeammate();
      unsubMessage();
    };
  }, [teamId]);
}

/**
 * 全局实时更新 Hook
 * 不限制团队 ID，接收所有更新
 */
export function useGlobalRealtimeUpdates(callbacks: {
  onTaskUpdate?: (teamId: string, task: IAgentTask) => void;
  onMessageReceived?: (teamId: string, message: IAgentTeamMessage) => void;
  onTeamUpdate?: (teamId: string, team: IAgentTeam) => void;
}) {
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  useEffect(() => {
    const unsubTask = ipcBridge.agentTeams.onTaskUpdate.on(({ team_id, task }) => {
      callbacksRef.current.onTaskUpdate?.(team_id, task);
    });

    const unsubMessage = ipcBridge.agentTeams.onMessageReceived.on(({ team_id, message }) => {
      callbacksRef.current.onMessageReceived?.(team_id, message);
    });

    const unsubTeam = ipcBridge.agentTeams.onTeamUpdate.on(({ team_id, team }) => {
      callbacksRef.current.onTeamUpdate?.(team_id, team);
    });

    return () => {
      unsubTask();
      unsubMessage();
      unsubTeam();
    };
  }, []);
}
