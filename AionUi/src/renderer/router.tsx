import React from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppLoader from './components/AppLoader';
import { useAuth } from './context/AuthContext';
import Conversation from './pages/conversation';
import Guid from './pages/guid';
import About from './pages/settings/About';
import AgentSettings from './pages/settings/AgentSettings';
import DisplaySettings from './pages/settings/DisplaySettings';
import GeminiSettings from './pages/settings/GeminiSettings';
import ModeSettings from './pages/settings/ModeSettings';
import SecuritySettings from './pages/settings/SecuritySettings';
import SystemSettings from './pages/settings/SystemSettings';
import ToolsSettings from './pages/settings/ToolsSettings';
import WebuiSettings from './pages/settings/WebuiSettings';
import HivemindSettings from './pages/settings/HivemindSettings';
import LoginPage from './pages/login';
import ComponentsShowcase from './pages/test/ComponentsShowcase';
import MonitorLayout from './pages/monitor/MonitorLayout';
import Dashboard from './pages/monitor/Dashboard';
import CacheManager from './pages/monitor/CacheManager';
import TaskQueue from './pages/monitor/TaskQueue';
import KnowledgeHub from './pages/knowledge';
import MemoryHub from './pages/memory';
import AgentTeamsLayout from './pages/agentTeams';
import AgentTeamsDashboard from './pages/agentTeams/Dashboard';
import TeamsPage from './pages/agentTeams/TeamsPage';
import TeamDetailPage from './pages/agentTeams/TeamDetailPage';
import TasksKanbanPage from './pages/agentTeams/TasksKanbanPage';
import TaskDetailPage from './pages/agentTeams/TaskDetailPage';
import AgentTeamsMonitorDashboard from './pages/agentTeams/MonitorDashboard';
import AgentTeamsAnalyticsPage from './pages/agentTeams/AnalyticsPage';

const ProtectedLayout: React.FC<{ layout: React.ReactElement }> = ({ layout }) => {
  const { status } = useAuth();

  if (status === 'checking') {
    return <AppLoader />;
  }

  if (status !== 'authenticated') {
    return <Navigate to='/login' replace />;
  }

  return React.cloneElement(layout);
};

const PanelRoute: React.FC<{ layout: React.ReactElement }> = ({ layout }) => {
  const { status } = useAuth();

  return (
    <HashRouter>
      <Routes>
        <Route path='/login' element={status === 'authenticated' ? <Navigate to='/guid' replace /> : <LoginPage />} />
        <Route element={<ProtectedLayout layout={layout} />}>
          <Route index element={<Navigate to='/guid' replace />} />
          <Route path='/guid' element={<Guid />} />
          <Route path='/conversation/:id' element={<Conversation />} />

          <Route path='/monitor' element={<MonitorLayout />}>
            <Route index element={<Dashboard />} />
            <Route path='stats' element={<Dashboard />} />
            <Route path='cache' element={<CacheManager />} />
            <Route path='tasks' element={<TaskQueue />} />
          </Route>
          <Route path='/knowledge' element={<KnowledgeHub />} />
          <Route path='/memory' element={<MemoryHub />} />

          <Route path='/agent-teams' element={<AgentTeamsLayout />}>
            <Route index element={<Navigate to='dashboard' replace />} />
            <Route path='dashboard' element={<AgentTeamsDashboard />} />
            <Route path='teams' element={<TeamsPage />} />
            <Route path='teams/:teamId' element={<TeamDetailPage />} />
            <Route path='tasks' element={<TasksKanbanPage />} />
            <Route path='tasks/:taskId' element={<TaskDetailPage />} />
            <Route path='monitor' element={<AgentTeamsMonitorDashboard />} />
            <Route path='analytics' element={<AgentTeamsAnalyticsPage />} />
          </Route>
          <Route path='/settings/gemini' element={<GeminiSettings />} />
          <Route path='/settings/model' element={<ModeSettings />} />
          <Route path='/settings/agent' element={<AgentSettings />} />
          <Route path='/settings/display' element={<DisplaySettings />} />
          <Route path='/settings/webui' element={<WebuiSettings />} />
          <Route path='/settings/hivemind' element={<HivemindSettings />} />
          <Route path='/settings/system' element={<SystemSettings />} />
          <Route path='/settings/about' element={<About />} />
          <Route path='/settings/tools' element={<ToolsSettings />} />
          <Route path='/settings/security' element={<SecuritySettings />} />
          <Route path='/settings' element={<Navigate to='/settings/hivemind' replace />} />
          <Route path='/test/components' element={<ComponentsShowcase />} />
        </Route>
        <Route path='*' element={<Navigate to={status === 'authenticated' ? '/guid' : '/login'} replace />} />
      </Routes>
    </HashRouter>
  );
};

export default PanelRoute;
