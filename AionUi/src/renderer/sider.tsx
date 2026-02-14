import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeftCircle,
  BookOpen,
  History,
  LayoutDashboard,
  Plus,
  Settings,
  Wrench,
} from 'lucide-react';
import WorkspaceGroupedHistory from './pages/conversation/WorkspaceGroupedHistory';
import SettingsSider from './pages/settings/SettingsSider';
import { iconColors } from './theme/colors';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/renderer/components/ui/tooltip';
import { usePreviewContext } from './pages/conversation/preview';

interface SiderProps {
  onSessionClick?: () => void;
  collapsed?: boolean;
}

const Sider: React.FC<SiderProps> = ({ onSessionClick, collapsed = false }) => {
  const location = useLocation();
  const { pathname, search, hash } = location;

  const { t } = useTranslation();
  const navigate = useNavigate();
  const { closePreview } = usePreviewContext();
  const isSettings = pathname.startsWith('/settings');
  const isMonitor = pathname.startsWith('/monitor');
  const isKnowledge = pathname.startsWith('/knowledge');
  const isMemory = pathname.startsWith('/memory');
  const isAgentTeams = pathname.startsWith('/agent-teams');
  const isSkills = pathname.startsWith('/skills');
  const lastNonSettingsPathRef = useRef('/guid');

  useEffect(() => {
    if (!pathname.startsWith('/settings')) {
      lastNonSettingsPathRef.current = `${pathname}${search}${hash}`;
    }
  }, [pathname, search, hash]);

  const handleSettingsClick = () => {
    if (isSettings) {
      const target = lastNonSettingsPathRef.current || '/guid';
      Promise.resolve(navigate(target)).catch((error) => {
        console.error('Navigation failed:', error);
      });
    } else {
      Promise.resolve(navigate('/settings/hivemind')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    }
    if (onSessionClick) {
      onSessionClick();
    }
  };

  const handleMonitorClick = () => {
    if (isMonitor) {
      Promise.resolve(navigate('/guid')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    } else {
      Promise.resolve(navigate('/monitor')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    }

    if (onSessionClick) {
      onSessionClick();
    }
  };

  const handleKnowledgeClick = () => {
    if (isKnowledge) {
      Promise.resolve(navigate('/guid')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    } else {
      Promise.resolve(navigate('/knowledge')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    }

    if (onSessionClick) {
      onSessionClick();
    }
  };

  const handleAgentTeamsClick = () => {
    if (isAgentTeams) {
      Promise.resolve(navigate('/guid')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    } else {
      Promise.resolve(navigate('/agent-teams/dashboard')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    }

    if (onSessionClick) {
      onSessionClick();
    }
  };

  const handleSkillsClick = () => {
    if (isSkills) {
      Promise.resolve(navigate('/guid')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    } else {
      Promise.resolve(navigate('/skills')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    }

    if (onSessionClick) {
      onSessionClick();
    }
  };

  const handleMemoryClick = () => {
    if (isMemory) {
      Promise.resolve(navigate('/guid')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    } else {
      Promise.resolve(navigate('/memory')).catch((error) => {
        console.error('Navigation failed:', error);
      });
    }

    if (onSessionClick) {
      onSessionClick();
    }
  };

  return (
    <TooltipProvider>
      <div className="size-full flex flex-col">
        {/* Main content area */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {isSettings ? (
            <SettingsSider collapsed={collapsed}></SettingsSider>
          ) : (
            <div className="size-full flex flex-col">
              <Tooltip>
                <TooltipTrigger asChild>
                  <div
                    className="flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer group shrink-0"
                    onClick={() => {
                      closePreview();
                      Promise.resolve(navigate('/guid')).catch((error) => {
                        console.error('Navigation failed:', error);
                      });
                      // 点击new chat后自动隐藏sidebar / Hide sidebar after starting new chat on mobile
                      if (onSessionClick) {
                        onSessionClick();
                      }
                    }}
                  >
                    <Plus
                      className="flex"
                      style={{ color: iconColors.primary }}
                      size={24}
                    />
                    <span className="collapsed-hidden font-bold text-t-primary">
                      {t('conversation.welcome.newConversation')}
                    </span>
                  </div>
                </TooltipTrigger>
                {collapsed && (
                  <TooltipContent side="right">
                    {t('conversation.welcome.newConversation')}
                  </TooltipContent>
                )}
              </Tooltip>
              <WorkspaceGroupedHistory
                collapsed={collapsed}
                onSessionClick={onSessionClick}
              ></WorkspaceGroupedHistory>
            </div>
          )}
        </div>
        {/* Footer - Knowledge Hub button */}
        <div className="shrink-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                onClick={handleKnowledgeClick}
                className="flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer"
              >
                <BookOpen className="flex text-22px" />
                <span className="collapsed-hidden text-t-primary">
                  {t('knowledge.title', { defaultValue: 'Knowledge Hub' })}
                </span>
              </div>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right">
                {t('knowledge.title', { defaultValue: 'Knowledge Hub' })}
              </TooltipContent>
            )}
          </Tooltip>
        </div>
        {/* Footer - Memory Hub button */}
        <div className="shrink-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                onClick={handleMemoryClick}
                className="flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer"
              >
                <History className="flex text-22px" />
                <span className="collapsed-hidden text-t-primary">
                  {t('memory.title')}
                </span>
              </div>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right">{t('memory.title')}</TooltipContent>
            )}
          </Tooltip>
        </div>
        {/* Footer - monitor button */}
        <div className="shrink-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                onClick={handleMonitorClick}
                className="flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer"
              >
                <LayoutDashboard className="flex text-22px" />
                <span className="collapsed-hidden text-t-primary">
                  {t('monitor.title', { defaultValue: 'Monitor' })}
                </span>
              </div>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right">
                {t('monitor.title', { defaultValue: 'Monitor' })}
              </TooltipContent>
            )}
          </Tooltip>
        </div>

        {/* Footer - Skills button */}
        <div className="shrink-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                onClick={handleSkillsClick}
                className="flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer"
              >
                <Wrench
                  className="flex"
                  style={{ color: iconColors.primary }}
                  size={22}
                />
                <span className="collapsed-hidden text-t-primary">
                  {t('skills.title', { defaultValue: 'Skills' })}
                </span>
              </div>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right">
                {t('skills.title', { defaultValue: 'Skills' })}
              </TooltipContent>
            )}
          </Tooltip>
        </div>

        {/* Footer - Agent Teams button */}
        <div className="shrink-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                onClick={handleAgentTeamsClick}
                className="flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer"
              >
                <LayoutDashboard className="flex text-22px" />
                <span className="collapsed-hidden text-t-primary">
                  {t('agentTeams.title', { defaultValue: 'Agent Teams' })}
                </span>
              </div>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right">
                {t('agentTeams.title', { defaultValue: 'Agent Teams' })}
              </TooltipContent>
            )}
          </Tooltip>
        </div>

        {/* Footer - settings button */}
        <div className="shrink-0 sider-footer">
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                onClick={handleSettingsClick}
                className="flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer"
              >
                {isSettings ? (
                  <ArrowLeftCircle
                    className="flex"
                    style={{ color: iconColors.primary }}
                    size={24}
                  />
                ) : (
                  <Settings
                    className="flex"
                    style={{ color: iconColors.primary }}
                    size={24}
                  />
                )}
                <span className="collapsed-hidden text-t-primary">
                  {isSettings ? t('common.back') : t('common.settings')}
                </span>
              </div>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right">
                {isSettings ? t('common.back') : t('common.settings')}
              </TooltipContent>
            )}
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  );
};

export default Sider;
