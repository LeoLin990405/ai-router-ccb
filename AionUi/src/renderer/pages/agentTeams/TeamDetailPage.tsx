/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/renderer/components/ui/button';
import { Input } from '@/renderer/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/renderer/components/ui/card';
import { Badge } from '@/renderer/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/renderer/components/ui/tabs';
import { motion, AnimatePresence } from 'framer-motion';
import { ipcBridge } from '@/common';
import type { IAgentCostAnalysis, IAgentTask, IAgentTeam, IAgentTeamMessage, IAgentTeamStats, IAgentTeammate } from '@/common/ipcBridge';
import { agentTeamsApi } from './api';
import { 
  StatBadge, 
  OverviewTab, 
  TasksTab, 
  MessagesTab, 
  AnalyticsTab 
} from './components';
import { Typography } from '@/renderer/components/atoms/Typography';

const TeamDetailPage: React.FC = () => {
  const { teamId } = useParams<{ teamId: string }>();
  const [loading, setLoading] = useState(true);
  const [team, setTeam] = useState<IAgentTeam | null>(null);
  const [teammates, setTeammates] = useState<IAgentTeammate[]>([]);
  const [tasks, setTasks] = useState<IAgentTask[]>([]);
  const [messages, setMessages] = useState<IAgentTeamMessage[]>([]);
  const [stats, setStats] = useState<IAgentTeamStats | null>(null);
  const [cost, setCost] = useState<IAgentCostAnalysis | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [updates, setUpdates] = useState<string[]>([]);

  // Add teammate form state
  const [teammateName, setTeammateName] = useState('');
  const [teammateRole, setTeammateRole] = useState('');
  const [teammateProvider, setTeammateProvider] = useState('');
  const [teammateModel, setTeammateModel] = useState('');

  const sortedTasks = useMemo(() => {
    return [...tasks].sort((a, b) => b.priority - a.priority || a.created_at - b.created_at);
  }, [tasks]);

  const refresh = async () => {
    if (!teamId) return;
    setLoading(true);
    try {
      const [nextTeam, nextTeammates, nextTasks, nextMessages, nextStats, nextCost] = await Promise.all([
        agentTeamsApi.getTeam(teamId),
        agentTeamsApi.listTeammates(teamId),
        agentTeamsApi.listTasks(teamId),
        agentTeamsApi.getMessages(teamId),
        agentTeamsApi.getTeamStats(teamId),
        agentTeamsApi.getCostAnalysis(teamId),
      ]);
      setTeam(nextTeam);
      setTeammates(nextTeammates);
      setTasks(nextTasks);
      setMessages(nextMessages);
      setStats(nextStats);
      setCost(nextCost);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickCreateTask = async () => {
    if (!teamId) return;
    try {
      await agentTeamsApi.createTask({
        team_id: teamId,
        subject: 'New coordination task',
        description: 'Added from overview',
        priority: 5,
      });
      await refresh();
    } catch (error) {
      console.error('Failed to create task');
    }
  };

  const addTeammate = async () => {
    if (!teamId) return;
    if (!teammateName.trim() || !teammateRole.trim() || !teammateProvider.trim() || !teammateModel.trim()) {
      return;
    }
    try {
      await agentTeamsApi.addTeammate({
        team_id: teamId,
        name: teammateName,
        role: teammateRole,
        provider: teammateProvider,
        model: teammateModel,
        skills: [],
      });
      setTeammateName('');
      setTeammateRole('');
      setTeammateProvider('');
      setTeammateModel('');
      await refresh();
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    void refresh();
  }, [teamId]);

  useEffect(() => {
    if (!teamId) return;

    const unsubscribeTeam = ipcBridge.agentTeams.onTeamUpdate.on(({ team_id, team: nextTeam }) => {
      if (team_id === teamId) setTeam(nextTeam);
    });

    const unsubscribeTask = ipcBridge.agentTeams.onTaskUpdate.on(({ team_id, task }) => {
      if (team_id === teamId) {
        setTasks(prev => [task, ...prev.filter(t => t.id !== task.id)]);
        setUpdates(prev => [`Task "${task.subject}" updated`, ...prev].slice(0, 3));
        setTimeout(() => setUpdates(prev => prev.slice(0, -1)), 3000);
      }
    });

    const unsubscribeTeammate = ipcBridge.agentTeams.onTeammateUpdate.on(({ team_id, teammate }) => {
      if (team_id === teamId) {
        setTeammates(prev => [teammate, ...prev.filter(t => t.id !== teammate.id)]);
      }
    });

    const unsubscribeMessage = ipcBridge.agentTeams.onMessageReceived.on(({ team_id, message }) => {
      if (team_id === teamId) {
        setMessages(prev => [message, ...prev.filter(m => m.id !== message.id)].slice(0, 200));
      }
    });

    return () => {
      unsubscribeTeam();
      unsubscribeTask();
      unsubscribeTeammate();
      unsubscribeMessage();
    };
  }, [teamId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!team) {
    return <Card><CardContent>Team not found</CardContent></Card>;
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="h-full flex flex-col"
      style={{ padding: '24px', height: '100%', overflowY: 'auto' }}
    >
      {/* Real-time Updates Toast */}
      <div style={{ position: 'fixed', top: 80, right: 24, zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <AnimatePresence>
          {updates.map((update, idx) => (
            <motion.div
              key={`${update}-${idx}`}
              initial={{ x: 100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 100, opacity: 0 }}
              style={{
                background: 'var(--color-primary)',
                color: 'white',
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-lg)',
                fontSize: '13px',
                fontWeight: 500
              }}
            >
              {update}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Typography variant="h3" bold>{team.name}</Typography>
          <Typography variant="body2" color="secondary" style={{ marginTop: '4px' }}>{team.description || 'No description provided'}</Typography>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Badge variant={team.status === 'active' ? 'default' : 'secondary'} className="text-sm px-3 py-1">
            {team.status.toUpperCase()}
          </Badge>
          <Button 
            onClick={async () => {
              const result = await agentTeamsApi.runTeam(team.id);
              await refresh();
            }}
          >
            Run Team
          </Button>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <StatBadge label="Teammates" value={teammates.length} />
        <StatBadge label="Total Tasks" value={stats?.total_tasks || 0} />
        <StatBadge label="Completed" value={stats?.completed_tasks || 0} color="success" />
        <StatBadge label="Total Cost" value={`$${team.total_cost_usd.toFixed(4)}`} color="warning" />
      </div>

      <Card>
        <CardContent className="p-0">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="px-5 pt-2">
              <TabsTrigger value="overview">
                <Typography variant="body2" bold={activeTab === 'overview'}>Overview</Typography>
              </TabsTrigger>
              <TabsTrigger value="teammates">
                <Typography variant="body2" bold={activeTab === 'teammates'}>{`Teammates (${teammates.length})`}</Typography>
              </TabsTrigger>
              <TabsTrigger value="tasks">
                <Typography variant="body2" bold={activeTab === 'tasks'}>{`Tasks (${tasks.length})`}</Typography>
              </TabsTrigger>
              <TabsTrigger value="messages">
                <Typography variant="body2" bold={activeTab === 'messages'}>Messages</Typography>
              </TabsTrigger>
              <TabsTrigger value="analytics">
                <Typography variant="body2" bold={activeTab === 'analytics'}>Analytics</Typography>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="p-0">
              <OverviewTab 
                team={team} 
                stats={stats} 
                onRefresh={refresh} 
                onQuickCreateTask={handleQuickCreateTask} 
              />
            </TabsContent>

            <TabsContent value="teammates">
              <div style={{ padding: '24px 0' }}>
                <Card className="mb-6">
                  <CardHeader>
                    <CardTitle>
                      <Typography variant="h6">Add New Teammate</Typography>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-end gap-2">
                      <Input
                        placeholder="Name"
                        value={teammateName}
                        onChange={(e) => setTeammateName(e.target.value)}
                      />
                      <Input
                        placeholder="Role"
                        value={teammateRole}
                        onChange={(e) => setTeammateRole(e.target.value)}
                      />
                      <Input
                        placeholder="Provider"
                        value={teammateProvider}
                        onChange={(e) => setTeammateProvider(e.target.value)}
                      />
                      <Input
                        placeholder="Model"
                        value={teammateModel}
                        onChange={(e) => setTeammateModel(e.target.value)}
                      />
                      <Button onClick={() => void addTeammate()}>Add</Button>
                    </div>
                  </CardContent>
                </Card>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                  {teammates.map(teammate => (
                    <motion.div 
                      key={teammate.id} 
                      whileHover={{ y: -4 }} 
                      style={{ padding: 16, background: 'var(--bg-1)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', boxShadow: 'var(--shadow-sm)' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <Typography variant="body1" bold>{teammate.name}</Typography>
                        <Badge variant={teammate.status === 'idle' ? 'default' : 'secondary'}>{teammate.status}</Badge>
                      </div>
                      <Typography variant="body2" color="secondary">{teammate.role}</Typography>
                      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <Badge variant="outline">{teammate.provider}</Badge>
                        <Badge variant="outline">{teammate.model}</Badge>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="tasks">
              <TasksTab tasks={sortedTasks} />
            </TabsContent>

            <TabsContent value="messages">
              <MessagesTab messages={messages} />
            </TabsContent>

            <TabsContent value="analytics">
              <AnalyticsTab stats={stats} cost={cost} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default TeamDetailPage;
