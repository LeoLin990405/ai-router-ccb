/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/renderer/components/ui/tooltip';
import WorkspaceGroupedHistory from '@/renderer/pages/conversation/WorkspaceGroupedHistory';
import { usePreviewContext } from '@/renderer/pages/conversation/preview';
import SettingsSider from '@/renderer/pages/settings/SettingsSider';
import classNames from 'classnames';
import { ArrowLeftCircle, BookOpen, Bot, History, LayoutDashboard, Plus, Settings, Wrench } from 'lucide-react';
import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';

interface SidebarNavProps {
  collapsed: boolean;
  onSessionClick?: () => void;
}

interface NavItemProps {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  collapsed: boolean;
  active?: boolean;
  primary?: boolean;
  className?: string;
}

const NavItem: React.FC<NavItemProps> = ({ label, icon, onClick, collapsed, active = false, primary = false, className }) => {
  const content = (
    <div
      onClick={onClick}
      className={classNames('hive-nav-item', className, {
        'hive-nav-item--active': active,
        'hive-nav-item--primary': primary,
        'hive-nav-item--collapsed': collapsed,
      })}
    >
      <span className='hive-nav-item__icon'>{icon}</span>
      <span className='hive-nav-item__label collapsed-hidden'>{label}</span>
    </div>
  );

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      {collapsed && <TooltipContent side='right'>{label}</TooltipContent>}
    </Tooltip>
  );
};

const SidebarNav: React.FC<SidebarNavProps> = ({ collapsed, onSessionClick }) => {
  const location = useLocation();
  const { pathname, search, hash } = location;
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { closePreview } = usePreviewContext();

  const isSettings = pathname.startsWith('/settings');
  const isMonitor = pathname.startsWith('/monitor');
  const isKnowledge = pathname.startsWith('/knowledge');
  const isMemory = pathname.startsWith('/memory');
  const isHivemind = pathname.startsWith('/guid') || pathname.startsWith('/conversation') || pathname.startsWith('/agent-teams');
  const isSkills = pathname.startsWith('/skills');
  const lastNonSettingsPathRef = useRef('/guid');

  useEffect(() => {
    if (!pathname.startsWith('/settings')) {
      lastNonSettingsPathRef.current = `${pathname}${search}${hash}`;
    }
  }, [pathname, search, hash]);

  const safeNavigate = (target: string) => {
    Promise.resolve(navigate(target)).catch((error) => console.error('Navigation failed:', error));
    onSessionClick?.();
  };

  const handleSettingsClick = () => {
    if (isSettings) {
      safeNavigate(lastNonSettingsPathRef.current || '/guid');
      return;
    }
    safeNavigate('/settings/hivemind');
  };

  return (
    <TooltipProvider>
      <div className='size-full flex flex-col hive-nav'>
        <div className='flex-1 min-h-0 overflow-y-auto'>
          {isSettings ? (
            <SettingsSider collapsed={collapsed} />
          ) : (
            <div className='size-full flex flex-col'>
              <NavItem
                label={t('conversation.welcome.newConversation')}
                icon={<Plus size={20} />}
                collapsed={collapsed}
                primary
                className='mb-10px'
                onClick={() => {
                  closePreview();
                  safeNavigate('/guid');
                }}
              />
              <WorkspaceGroupedHistory collapsed={collapsed} onSessionClick={onSessionClick} />
            </div>
          )}
        </div>

        <div className='hive-nav-section'>
          <NavItem label={t('knowledge.title', { defaultValue: 'Knowledge Hub' })} icon={<BookOpen size={20} />} collapsed={collapsed} active={isKnowledge} onClick={() => safeNavigate(isKnowledge ? '/guid' : '/knowledge')} />
          <NavItem label={t('memory.title')} icon={<History size={20} />} collapsed={collapsed} active={isMemory} onClick={() => safeNavigate(isMemory ? '/guid' : '/memory')} />
          <NavItem label={t('settings.hivemind', { defaultValue: 'Hivemind' })} icon={<Bot size={20} />} collapsed={collapsed} active={isHivemind} onClick={() => safeNavigate('/agent-teams/chat')} />
          <NavItem label={t('skills.title', { defaultValue: 'Skills' })} icon={<Wrench size={20} />} collapsed={collapsed} active={isSkills} onClick={() => safeNavigate(isSkills ? '/guid' : '/skills')} />
          <NavItem label={t('monitor.title', { defaultValue: 'System Monitor' })} icon={<LayoutDashboard size={20} />} collapsed={collapsed} active={isMonitor} onClick={() => safeNavigate(isMonitor ? '/guid' : '/monitor')} />
        </div>

        <div className='hive-nav-section sider-footer'>
          <NavItem label={isSettings ? t('common.back') : t('common.settings')} icon={isSettings ? <ArrowLeftCircle size={20} /> : <Settings size={20} />} collapsed={collapsed} active={isSettings} onClick={handleSettingsClick} />
        </div>
      </div>
    </TooltipProvider>
  );
};

export { NavItem };
export default SidebarNav;
