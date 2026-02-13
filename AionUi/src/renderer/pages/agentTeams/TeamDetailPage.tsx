/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, Form, Input, Message, Spin, Tabs, Tag } from '@arco-design/web-react';
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

const { TabPane } = Tabs;

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
  const [form] = Form.useForm();
  const [updates, setUpdates] = useState<string[]>([]);

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
      Message.error(error instanceof Error ? error.message : String(error));
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
      Message.success('Task created');
      await refresh();
    } catch (error) {
      Message.error('Failed to create task');
    }
  };

  const addTeammate = async () => {
    if (!teamId) return;
    try {
      const values = await form.validate();
      await agentTeamsApi.addTeammate({
        team_id: teamId,
        name: values.name,
        role: values.role,
        provider: values.provider,
        model: values.model,
        skills: String(values.skills || '').split(',').map(s => s.trim()).filter(Boolean),
      });
      Message.success('Teammate added');
      form.resetFields();
      await refresh();
    } catch (error) {
      if (error instanceof Error) Message.error(error.message);
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
    return <div style={{ textAlign: 'center', padding: '48px 0' }}><Spin size={40} /></div>;
  }

  if (!team) {
    return <Card style={{ borderRadius: 'var(--radius-lg)' }}>Team not found</Card>;
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
          <Tag color={team.status === 'active' ? 'green' : 'orange'} style={{ borderRadius: 'var(--radius-sm)', padding: '4px 12px', height: 'auto' }}>
            {team.status.toUpperCase()}
          </Tag>
          <Button 
            status='success'
            type='primary'
            style={{ borderRadius: 'var(--radius-md)' }}
            onClick={async () => {
              const result = await agentTeamsApi.runTeam(team.id);
              Message.success(`Team run finished: started ${result.started}, completed ${result.completed}, failed ${result.failed}`);
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

      <Card 
        style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-md)' }}
        bodyStyle={{ padding: '0px' }}
      >
        <Tabs activeTab={activeTab} onChange={setActiveTab} type="line" style={{ padding: '0 20px' }}>
          <TabPane key='overview' title={<Typography variant="body2" bold={activeTab === 'overview'}>Overview</Typography>}>
            <OverviewTab 
              team={team} 
              stats={stats} 
              onRefresh={refresh} 
              onQuickCreateTask={handleQuickCreateTask} 
            />
          </TabPane>

          <TabPane key='teammates' title={<Typography variant="body2" bold={activeTab === 'teammates'}>{`Teammates (${teammates.length})`}</Typography>}>
            <div style={{ padding: '24px 0' }}>
              <Card title={<Typography variant="h6">Add New Teammate</Typography>} style={{ marginBottom: 24, borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                <Form form={form} layout='inline'>
                  <Form.Item field='name' rules={[{ required: true }]}><Input placeholder='Name' /></Form.Item>
                  <Form.Item field='role' rules={[{ required: true }]}><Input placeholder='Role' /></Form.Item>
                  <Form.Item field='provider' rules={[{ required: true }]}><Input placeholder='Provider' /></Form.Item>
                  <Form.Item field='model' rules={[{ required: true }]}><Input placeholder='Model' /></Form.Item>
                  <Form.Item><Button type='primary' onClick={() => void addTeammate()}>Add</Button></Form.Item>
                </Form>
              </Card>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                {teammates.map(teammate => (
                  <motion.div key={teammate.id} whileHover={{ y: -4 }} style={{ padding: 16, background: 'var(--bg-1)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', boxShadow: 'var(--shadow-sm)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <Typography variant="body1" bold>{teammate.name}</Typography>
                      <Tag color={teammate.status === 'idle' ? 'green' : 'orange'} style={{ borderRadius: 'var(--radius-sm)' }}>{teammate.status}</Tag>
                    </div>
                    <Typography variant="body2" color="secondary">{teammate.role}</Typography>
                    <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <Tag size="small">{teammate.provider}</Tag>
                      <Tag size="small">{teammate.model}</Tag>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </TabPane>

          <TabPane key='tasks' title={<Typography variant="body2" bold={activeTab === 'tasks'}>{`Tasks (${tasks.length})`}</Typography>}>
            <TasksTab tasks={sortedTasks} />
          </TabPane>

          <TabPane key='messages' title={<Typography variant="body2" bold={activeTab === 'messages'}>Messages</Typography>}>
            <MessagesTab messages={messages} />
          </TabPane>

          <TabPane key='analytics' title={<Typography variant="body2" bold={activeTab === 'analytics'}>Analytics</Typography>}>
            <AnalyticsTab stats={stats} cost={cost} />
          </TabPane>
        </Tabs>
      </Card>
    </motion.div>
  );
};

export default TeamDetailPage;
