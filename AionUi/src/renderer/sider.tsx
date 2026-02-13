import { ArrowCircleLeft, Plus, SettingTwo } from '@icon-park/react';
import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import WorkspaceGroupedHistory from './pages/conversation/WorkspaceGroupedHistory';
import SettingsSider from './pages/settings/SettingsSider';
import { iconColors } from './theme/colors';
import { Tooltip } from '@arco-design/web-react';
import { IconDashboard, IconBook, IconHistory } from '@arco-design/web-react/icon';
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
    <div className='size-full flex flex-col'>
      {/* Main content area */}
      <div className='flex-1 min-h-0 overflow-hidden'>
        {isSettings ? (
          <SettingsSider collapsed={collapsed}></SettingsSider>
        ) : (
          <div className='size-full flex flex-col'>
            <Tooltip disabled={!collapsed} content={t('conversation.welcome.newConversation')} position='right'>
              <div
                className='flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer group shrink-0'
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
                <Plus theme='outline' size='24' fill={iconColors.primary} className='flex' />
                <span className='collapsed-hidden font-bold text-t-primary'>{t('conversation.welcome.newConversation')}</span>
              </div>
            </Tooltip>
            <WorkspaceGroupedHistory collapsed={collapsed} onSessionClick={onSessionClick}></WorkspaceGroupedHistory>
          </div>
        )}
      </div>
      {/* Footer - Knowledge Hub button */}
      <div className='shrink-0'>
        <Tooltip disabled={!collapsed} content={t('knowledge.title', { defaultValue: 'Knowledge Hub' })} position='right'>
          <div onClick={handleKnowledgeClick} className='flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer'>
            <IconBook className='flex text-22px' />
            <span className='collapsed-hidden text-t-primary'>{t('knowledge.title', { defaultValue: 'Knowledge Hub' })}</span>
          </div>
        </Tooltip>
      </div>
      {/* Footer - Memory Hub button */}
      <div className='shrink-0'>
        <Tooltip disabled={!collapsed} content={t('memory.title')} position='right'>
          <div onClick={handleMemoryClick} className='flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer'>
            <IconHistory className='flex text-22px' />
            <span className='collapsed-hidden text-t-primary'>{t('memory.title')}</span>
          </div>
        </Tooltip>
      </div>
      {/* Footer - monitor button */}
      <div className='shrink-0'>
        <Tooltip disabled={!collapsed} content={t('monitor.title', { defaultValue: 'Monitor' })} position='right'>
          <div onClick={handleMonitorClick} className='flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer'>
            <IconDashboard className='flex text-22px' />
            <span className='collapsed-hidden text-t-primary'>{t('monitor.title', { defaultValue: 'Monitor' })}</span>
          </div>
        </Tooltip>
      </div>

      {/* Footer - Agent Teams button */}
      <div className='shrink-0'>
        <Tooltip disabled={!collapsed} content={t('agentTeams.title', { defaultValue: 'Agent Teams' })} position='right'>
          <div onClick={handleAgentTeamsClick} className='flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer'>
            <IconDashboard className='flex text-22px' />
            <span className='collapsed-hidden text-t-primary'>{t('agentTeams.title', { defaultValue: 'Agent Teams' })}</span>
          </div>
        </Tooltip>
      </div>

      {/* Footer - settings button */}
      <div className='shrink-0 sider-footer'>
        <Tooltip disabled={!collapsed} content={isSettings ? t('common.back') : t('common.settings')} position='right'>
          <div onClick={handleSettingsClick} className='flex items-center justify-start gap-10px px-12px py-8px hover:bg-hover rd-0.5rem mb-8px cursor-pointer'>
            {isSettings ? <ArrowCircleLeft className='flex' theme='outline' size='24' fill={iconColors.primary} /> : <SettingTwo className='flex' theme='outline' size='24' fill={iconColors.primary} />}
            <span className='collapsed-hidden text-t-primary'>{isSettings ? t('common.back') : t('common.settings')}</span>
          </div>
        </Tooltip>
      </div>
    </div>
  );
};

export default Sider;
