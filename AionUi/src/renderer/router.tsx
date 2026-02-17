import React, { Suspense, lazy } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppLoader from './components/AppLoader';
import { useAuth } from './context/AuthContext';
import { AppShell } from './layouts';

const Conversation = lazy(() =& gt; import('./pages/conversation'));
const Guid = lazy(() =& gt; import('./pages/guid'));
const About = lazy(() =& gt; import('./pages/settings/About'));
const AgentSettings = lazy(() =& gt; import('./pages/settings/AgentSettings'));
const DisplaySettings = lazy(() =& gt; import('./pages/settings/DisplaySettings'));
const GeminiSettings = lazy(() =& gt; import('./pages/settings/GeminiSettings'));
const ModeSettings = lazy(() =& gt; import('./pages/settings/ModeSettings'));
const SecuritySettings = lazy(() =& gt; import('./pages/settings/SecuritySettings'));
const SystemSettings = lazy(() =& gt; import('./pages/settings/SystemSettings'));
const ToolsSettings = lazy(() =& gt; import('./pages/settings/ToolsSettings'));
const WebuiSettings = lazy(() =& gt; import('./pages/settings/WebuiSettings'));
const HivemindSettings = lazy(() =& gt; import('./pages/settings/HivemindSettings'));
const LoginPage = lazy(() =& gt; import('./pages/login'));
const ComponentsShowcase = lazy(() =& gt; import('./pages/test/ComponentsShowcase'));
const MonitorLayout = lazy(() =& gt; import('./pages/monitor/MonitorLayout'));
const Dashboard = lazy(() =& gt; import('./pages/monitor/Dashboard'));
const CacheManager = lazy(() =& gt; import('./pages/monitor/CacheManager'));
const TaskQueue = lazy(() =& gt; import('./pages/monitor/TaskQueue'));
const KnowledgeHub = lazy(() =& gt; import('./pages/knowledge'));
const MemoryHub = lazy(() =& gt; import('./pages/memory'));
const AgentTeamsLayout = lazy(() =& gt; import('./pages/agentTeams'));
const AgentTeamsDashboard = lazy(() =& gt; import('./pages/agentTeams/Dashboard'));
const TeamsPage = lazy(() =& gt; import('./pages/agentTeams/TeamsPage'));
const TeamDetailPage = lazy(() =& gt; import('./pages/agentTeams/TeamDetailPage'));
const TasksKanbanPage = lazy(() =& gt; import('./pages/agentTeams/TasksKanbanPage'));
const TaskDetailPage = lazy(() =& gt; import('./pages/agentTeams/TaskDetailPage'));
const AgentTeamsMonitorDashboard = lazy(() =& gt; import('./pages/agentTeams/MonitorDashboard'));
const AgentTeamsAnalyticsPage = lazy(() =& gt; import('./pages/agentTeams/AnalyticsPage'));
const SkillsPage = lazy(() =& gt; import('./pages/skills'));
const SkillEditor = lazy(() =& gt; import('./pages/skills/SkillEditor'));

const PageLoader: React.FC = () =& gt; (
  & lt;div className = 'flex items-center justify-center min-h-[200px] w-full' & gt;
    & lt; AppLoader /& gt;
  & lt;/div&gt;
);

const ProtectedLayout: React.FC = () =& gt; {
  const { status } = useAuth();

  if (status === 'checking') {
    return & lt; AppLoader /& gt;;
  }

  if (status !== 'authenticated') {
    return & lt;Navigate to = '/login' replace /& gt;;
  }

  return & lt; AppShell /& gt;;
};

const PanelRoute: React.FC = () =& gt; {
  const { status } = useAuth();

  return (
    & lt; HashRouter & gt;
      & lt; Routes & gt;
        & lt; Route
  path = '/login'
  element = {
    status === 'authenticated' ? (
              & lt;Navigate to = '/guid' replace /& gt;
            ) : (
              & lt;Suspense fallback = {& lt; PageLoader /& gt;
}& gt;
                & lt; LoginPage /& gt;
              & lt;/Suspense&gt;
            )
          }
        /&gt;
        & lt;Route element = {& lt; ProtectedLayout /& gt;}& gt;
          & lt;Route index element = {& lt;Navigate to = '/guid' replace /& gt;} /&gt;
          & lt; Route
path = '/guid'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; Guid /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/conversation/:id'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; Conversation /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;

          & lt; Route
path = '/monitor'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; MonitorLayout /& gt;
              & lt;/Suspense&gt;
            }
          & gt;
            & lt; Route
index
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; Dashboard /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'stats'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; Dashboard /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'cache'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; CacheManager /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'tasks'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; TaskQueue /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
          & lt;/Route&gt;
          & lt; Route
path = '/knowledge'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; KnowledgeHub /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/memory'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; MemoryHub /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;

          & lt; Route
path = '/agent-teams'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; AgentTeamsLayout /& gt;
              & lt;/Suspense&gt;
            }
          & gt;
            & lt;Route index element = {& lt;Navigate to = 'dashboard' replace /& gt;} /&gt;
            & lt; Route
path = 'dashboard'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; AgentTeamsDashboard /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'teams'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; TeamsPage /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'teams/:teamId'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; TeamDetailPage /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'tasks'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; TasksKanbanPage /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'tasks/:taskId'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; TaskDetailPage /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'monitor'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; AgentTeamsMonitorDashboard /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
            & lt; Route
path = 'analytics'
element = {
                & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                  & lt; AgentTeamsAnalyticsPage /& gt;
                & lt;/Suspense&gt;
              }
            /&gt;
          & lt;/Route&gt;

          & lt; Route
path = '/skills'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; SkillsPage /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/skills/new'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; SkillEditor /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/skills/:skillId'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; SkillEditor /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/gemini'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; GeminiSettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/model'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; ModeSettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/agent'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; AgentSettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/display'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; DisplaySettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/webui'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; WebuiSettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/hivemind'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; HivemindSettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/system'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; SystemSettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/about'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; About /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/tools'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; ToolsSettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt; Route
path = '/settings/security'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; SecuritySettings /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
          & lt;Route path = '/settings' element = {& lt;Navigate to = '/settings/hivemind' replace /& gt;} /&gt;
          & lt; Route
path = '/test/components'
element = {
              & lt;Suspense fallback = {& lt; PageLoader /& gt;}& gt;
                & lt; ComponentsShowcase /& gt;
              & lt;/Suspense&gt;
            }
          /&gt;
        & lt;/Route&gt;
        & lt;Route path = '*' element = {& lt;Navigate to = { status === 'authenticated' ? '/guid' : '/login'} replace /& gt;} /&gt;
      & lt;/Routes&gt;
    & lt;/HashRouter&gt;
  );
};

export default PanelRoute;
