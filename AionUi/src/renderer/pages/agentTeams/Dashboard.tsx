/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, Grid, Space, Spin, Table, Tag, Button } from '@arco-design/web-react';
import { People, CheckCorrect, ApplicationOne, PayCode } from '@icon-park/react';
import { agentTeamsApi } from './api';
import { ipcBridge } from '@/common';
import type { IAgentTeam, IAgentTask } from '@/common/ipcBridge';
import { Typography } from '@/renderer/components/atoms/Typography';
import { StatCard } from '@/renderer/components/molecules/StatCard';
import { ActivityTimeline, Activity } from '@/renderer/components/organisms/ActivityTimeline';
import { PerformanceChart } from '@/renderer/components/organisms/PerformanceChart';
import IconParkHOC from '@/renderer/components/IconParkHOC';

const { Row, Col } = Grid;

const IconPeople = IconParkHOC(People);
const IconCheck = IconParkHOC(CheckCorrect);
const IconTasks = IconParkHOC(ApplicationOne);
const IconCost = IconParkHOC(PayCode);

// 动画配置
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: 'easeOut' as const,
    },
  },
};

// 扩展的 Dashboard 统计数据接口
interface DashboardStats {
  activeTeams: number;
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  totalCost: number;
  completedToday: number;
  completionTrend: Array<{
    date: string;
    completed: number;
    failed: number;
  }>;
}

const AgentTeamsDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<IAgentTeam[]>([]);
  const [tasks, setTasks] = useState<IAgentTask[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [stats, setStats] = useState<DashboardStats>({
    activeTeams: 0,
    totalTasks: 0,
    completedTasks: 0,
    failedTasks: 0,
    totalCost: 0,
    completedToday: 0,
    completionTrend: [],
  });

  // 生成趋势数据
  const generateTrendData = (allTasks: IAgentTask[]) => {
    const trend = [];
    for (let i = 6; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const dateStr = date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });

      const dayStart = new Date(date).setHours(0, 0, 0, 0);
      const dayEnd = new Date(date).setHours(23, 59, 59, 999);

      const completed = allTasks.filter(
        (t) => t.status === 'completed' && t.completed_at && t.completed_at >= dayStart && t.completed_at <= dayEnd
      ).length;

      const failed = allTasks.filter(
        (t) => t.status === 'failed' && t.completed_at && t.completed_at >= dayStart && t.completed_at <= dayEnd
      ).length;

      trend.push({ date: dateStr, completed, failed });
    }
    return trend;
  };

  // 加载 Dashboard 数据
  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // 获取所有团队
      const teamsResult = await agentTeamsApi.listTeams();
      const allTeams = teamsResult || [];
      setTeams(allTeams);

      // 计算统计数据
      const activeTeams = allTeams.filter((t) => t.status === 'active').length;

      // 获取所有任务
      const tasksPromises = allTeams.map((team) => agentTeamsApi.listTasks(team.id));
      const tasksResults = await Promise.all(tasksPromises);
      const allTasks = tasksResults.flatMap((r) => r || []);
      setTasks(allTasks);

      const totalTasks = allTasks.length;
      const completedTasks = allTasks.filter((t) => t.status === 'completed').length;
      const failedTasks = allTasks.filter((t) => t.status === 'failed').length;

      // 计算今日完成的任务
      const today = new Date().setHours(0, 0, 0, 0);
      const completedToday = allTasks.filter(
        (t) => t.status === 'completed' && t.completed_at && t.completed_at >= today
      ).length;

      // 计算总成本
      const totalCost = allTasks.reduce((sum, t) => sum + (t.cost_usd || 0), 0);

      // 生成趋势数据
      const completionTrend = generateTrendData(allTasks);

      setStats({
        activeTeams,
        totalTasks,
        completedTasks,
        failedTasks,
        totalCost,
        completedToday,
        completionTrend,
      });
    } catch (error) {
      console.error('加载 Dashboard 数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 初始加载和实时更新监听
  useEffect(() => {
    void loadDashboardData();

    // 实时活动监听
    const unsubTask = ipcBridge.agentTeams.onTaskUpdate.on(({ task }) => {
      const newActivity: Activity = {
        id: `task-${task.id}-${Date.now()}`,
        type: 'task',
        action: '任务已更新',
        target: task.subject,
        time: Date.now(),
        status: task.status,
      };
      setActivities((prev) => [newActivity, ...prev].slice(0, 20));
      void loadDashboardData();
    });

    const unsubMessage = ipcBridge.agentTeams.onMessageReceived.on(({ message }) => {
      const newActivity: Activity = {
        id: `msg-${message.id}`,
        type: 'message',
        action: '新消息',
        target: message.content.substring(0, 50) + (message.content.length > 50 ? '...' : ''),
        time: message.created_at,
      };
      setActivities((prev) => [newActivity, ...prev].slice(0, 20));
    });

    const unsubTeam = ipcBridge.agentTeams.onTeamUpdate.on(({ team }) => {
      const newActivity: Activity = {
        id: `team-${team.id}-${Date.now()}`,
        type: 'team',
        action: '团队状态变更',
        target: team.name,
        time: Date.now(),
        status: team.status,
      };
      setActivities((prev) => [newActivity, ...prev].slice(0, 20));
      void loadDashboardData();
    });

    return () => {
      unsubTask();
      unsubMessage();
      unsubTeam();
    };
  }, []);

  // 图表数据
  const chartData = useMemo(() => {
    return teams
      .filter((t) => t.total_tasks > 0)
      .slice(0, 5)
      .map((t) => ({
        name: t.name,
        completed: t.completed_tasks,
        total: t.total_tasks,
      }));
  }, [teams]);

  // 活跃团队列表
  const activeTeams = useMemo(() => {
    return teams.filter((t) => t.status === 'active');
  }, [teams]);

  if (loading && teams.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Spin size={40} />
          <p className="mt-4 text-t-secondary">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="p-6 space-y-6 h-full overflow-y-auto"
    >
      {/* 欢迎头部 */}
      <motion.div variants={itemVariants} className="flex items-center justify-between mb-8">
        <div>
          <Typography variant="h3" bold className="text-t-primary">
            Agent Teams 仪表盘
          </Typography>
          <Typography variant="body2" color="secondary" className="mt-1">
            管理和监控你的 AI 协作团队
          </Typography>
        </div>
        <Button type="primary" onClick={() => void loadDashboardData()} className="rounded-lg">
          刷新数据
        </Button>
      </motion.div>

      {/* 快速统计卡片 */}
      <motion.div variants={itemVariants}>
        <Row gutter={[24, 24]}>
          <Col span={6}>
            <StatCard
              title="活跃团队"
              value={stats.activeTeams}
              icon={<IconPeople />}
              color="primary"
              trend={stats.activeTeams > 0 ? 100 : 0}
              trendLabel="占总团队比例"
            />
          </Col>
          <Col span={6}>
            <StatCard
              title="总任务数"
              value={stats.totalTasks}
              icon={<IconTasks />}
              color="warning"
            />
          </Col>
          <Col span={6}>
            <StatCard
              title="今日完成"
              value={stats.completedToday}
              icon={<IconCheck />}
              color="success"
            />
          </Col>
          <Col span={6}>
            <StatCard
              title="总成本"
              value={`$${stats.totalCost.toFixed(2)}`}
              icon={<IconCost />}
              color="error"
            />
          </Col>
        </Row>
      </motion.div>

      {/* 任务完成趋势图表 + 最近活动 */}
      <motion.div variants={itemVariants}>
        <Row gutter={[24, 24]} style={{ marginTop: '24px' }}>
          <Col span={14}>
            <Card
              title={<Typography variant="h6" bold>任务完成趋势</Typography>}
              className="rounded-xl shadow-sm border border-line-2 h-full"
            >
              {stats.completionTrend.length > 0 ? (
                <div className="h-64">
                  {/* 这里可以集成 Recharts 图表 */}
                  <div className="flex items-end justify-between h-full gap-4">
                    {stats.completionTrend.map((item, index) => (
                      <motion.div
                        key={item.date}
                        initial={{ height: 0 }}
                        animate={{ height: `${Math.max((item.completed / Math.max(...stats.completionTrend.map(t => t.completed), 1)) * 100, 10)}%` }}
                        transition={{ duration: 0.5, delay: index * 0.1 }}
                        className="flex-1 flex flex-col items-center"
                      >
                        <div className="w-full bg-primary/20 rounded-t-lg relative group cursor-pointer">
                          <div 
                            className="absolute bottom-0 w-full bg-primary rounded-t-lg transition-all"
                            style={{ height: `${Math.max((item.completed / Math.max(item.completed + item.failed, 1)) * 100, 20)}%` }}
                          />
                          {/* Tooltip */}
                          <div className="absolute -top-12 left-1/2 -translate-x-1/2 bg-bg-0 border border-line-2 rounded-lg px-2 py-1 text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 shadow-lg">
                            <div className="text-success">完成: {item.completed}</div>
                            <div className="text-error">失败: {item.failed}</div>
                          </div>
                        </div>
                        <span className="text-xs text-t-secondary mt-2">{item.date}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              ) : (
                <PerformanceChart data={chartData} />
              )}
            </Card>
          </Col>
          <Col span={10}>
            <ActivityTimeline activities={activities} />
          </Col>
        </Row>
      </motion.div>

      {/* 活跃团队列表 */}
      <motion.div variants={itemVariants}>
        <Card
          title={<Typography variant="h6" bold>活跃团队</Typography>}
          className="rounded-xl shadow-sm border border-line-2 mt-6"
          bodyStyle={{ padding: 0 }}
        >
          {activeTeams.length > 0 ? (
            <div className="divide-y divide-line-2">
              {activeTeams.map((team) => (
                <motion.div
                  key={team.id}
                  whileHover={{ backgroundColor: 'var(--bg-1)' }}
                  className="p-4 flex items-center justify-between cursor-pointer transition-colors"
                  onClick={() => window.location.hash = `/agent-teams/teams/${team.id}`}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <Typography variant="body2" bold className="text-t-primary">
                        {team.name}
                      </Typography>
                      <Tag color="green" size="small" className="rounded-sm">
                        ACTIVE
                      </Tag>
                    </div>
                    <Typography variant="caption" color="secondary" className="mt-1 block">
                      {team.description || '暂无描述'}
                    </Typography>
                  </div>
                  <div className="text-right flex items-center gap-8">
                    <div>
                      <Typography variant="caption" color="secondary">任务进度</Typography>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="w-24 h-2 bg-bg-2 rounded-full overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${team.total_tasks > 0 ? (team.completed_tasks / team.total_tasks) * 100 : 0}%` }}
                            transition={{ duration: 0.5 }}
                            className="h-full bg-success rounded-full"
                          />
                        </div>
                        <Typography variant="caption" className="text-t-secondary">
                          {team.completed_tasks}/{team.total_tasks}
                        </Typography>
                      </div>
                    </div>
                    <div>
                      <Typography variant="caption" color="secondary">成本</Typography>
                      <Typography variant="body2" bold className="text-t-primary">
                        ${team.total_cost_usd.toFixed(2)}
                      </Typography>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center">
              <Typography variant="body2" color="secondary">暂无活跃团队</Typography>
            </div>
          )}
        </Card>
      </motion.div>

      {/* 团队概览表格 */}
      <motion.div variants={itemVariants}>
        <Card
          title={<Typography variant="h6" bold>团队概览</Typography>}
          className="rounded-xl shadow-sm border border-line-2 mt-6"
          bodyStyle={{ padding: 0 }}
        >
          <Table
            rowKey="id"
            pagination={{ pageSize: 5 }}
            data={teams}
            columns={[
              {
                title: '团队名称',
                dataIndex: 'name',
                render: (name) => <Typography variant="body2" bold>{name}</Typography>,
              },
              {
                title: '状态',
                dataIndex: 'status',
                render: (status) => (
                  <Tag color={status === 'active' ? 'green' : 'orange'} className="rounded-sm">
                    {status.toUpperCase()}
                  </Tag>
                ),
              },
              { title: '总任务', dataIndex: 'total_tasks' },
              { title: '已完成', dataIndex: 'completed_tasks' },
              {
                title: '进度',
                render: (_, record) => {
                  const percent = record.total_tasks > 0 ? Math.round((record.completed_tasks / record.total_tasks) * 100) : 0;
                  return (
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-2 bg-bg-2 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                      <span className="text-xs text-t-secondary">{percent}%</span>
                    </div>
                  );
                },
              },
              {
                title: '成本',
                dataIndex: 'total_cost_usd',
                render: (cost) => `$${Number(cost).toFixed(2)}`,
              },
            ]}
          />
        </Card>
      </motion.div>
    </motion.div>
  );
};

export default AgentTeamsDashboard;
