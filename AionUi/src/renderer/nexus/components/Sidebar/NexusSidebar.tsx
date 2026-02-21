/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import classNames from 'classnames';
import { ArrowLeftCircle, BookOpen, Bot, History, LayoutDashboard, Plus, Settings, Wrench } from 'lucide-react';
import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import WorkspaceGroupedHistory from '@/renderer/pages/conversation/WorkspaceGroupedHistory';
import SettingsSider from '@/renderer/pages/settings/SettingsSider';
import { usePreviewContext } from '@/renderer/pages/conversation/preview';

interface NexusSidebarProps {
  onSessionClick?: () => void;
  collapsed?: boolean;
}

interface NexusNavItemProps {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  collapsed: boolean;
  active?: boolean;
  primary?: boolean;
}

const NexusNavItem: React.FC<NexusNavItemProps> = ({ label, icon, onClick, collapsed, active = false, primary = false }) => (
  <button
    type='button'
    className={classNames('nexus-nav-item', {
      'nexus-nav-item--active': active,
      'nexus-nav-item--primary': primary,
      'justify-center': collapsed,
    })}
    onClick={onClick}
  >
    <span className='shrink-0'>{icon}</span>
    {!collapsed && <span className='truncate'>{label}</span>}
  </button>
);

const NexusSidebar: React.FC<NexusSidebarProps> = ({ onSessionClick, collapsed = false }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { closePreview } = usePreviewContext();
  const { pathname, search, hash } = location;

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
    Promise.resolve(navigate(target)).catch((error) => {
      console.error('Navigation failed:', error);
    });
    onSessionClick?.();
  };

  return (
    <div className='size-full flex flex-col'>
      {!collapsed && (
        <div className='px-10px pt-10px pb-6px'>
          <div className='nexus-sider-kicker'>Orchestrator</div>
        </div>
      )}

      <div className='px-8px pb-8px'>
        <NexusNavItem
          label={t('conversation.welcome.newConversation')}
          icon={<Plus size={16} />}
          collapsed={collapsed}
          primary
          onClick={() => {
            closePreview();
            safeNavigate('/guid');
          }}
        />
      </div>

      <div className='flex-1 min-h-0 overflow-y-auto px-8px'>
        {isSettings ? (
          <SettingsSider collapsed={collapsed} />
        ) : (
          <>
            {!collapsed && <div className='nexus-nav-group-title'>Sessions</div>}
            <WorkspaceGroupedHistory collapsed={collapsed} onSessionClick={onSessionClick} />

            <div className='mt-10px border-t border-[var(--nexus-border-subtle)] pt-8px flex flex-col gap-4px'>
              {!collapsed && <div className='nexus-nav-group-title mt-0'>Spaces</div>}
              <NexusNavItem label={t('knowledge.title', { defaultValue: 'Knowledge Hub' })} icon={<BookOpen size={15} />} collapsed={collapsed} active={isKnowledge} onClick={() => safeNavigate(isKnowledge ? '/guid' : '/knowledge')} />
              <NexusNavItem label={t('memory.title')} icon={<History size={15} />} collapsed={collapsed} active={isMemory} onClick={() => safeNavigate(isMemory ? '/guid' : '/memory')} />
              <NexusNavItem label={t('settings.hivemind', { defaultValue: 'Hivemind' })} icon={<Bot size={15} />} collapsed={collapsed} active={isHivemind} onClick={() => safeNavigate('/agent-teams/chat')} />
              <NexusNavItem label={t('monitor.title', { defaultValue: 'System Monitor' })} icon={<LayoutDashboard size={15} />} collapsed={collapsed} active={isMonitor} onClick={() => safeNavigate(isMonitor ? '/guid' : '/monitor')} />
              <NexusNavItem label={t('skills.title', { defaultValue: 'Skills' })} icon={<Wrench size={15} />} collapsed={collapsed} active={isSkills} onClick={() => safeNavigate(isSkills ? '/guid' : '/skills')} />
            </div>
          </>
        )}
      </div>

      <div className='p-8px border-t border-[var(--nexus-border-subtle)]'>
        <NexusNavItem
          label={isSettings ? t('common.back') : t('common.settings')}
          icon={isSettings ? <ArrowLeftCircle size={15} /> : <Settings size={15} />}
          collapsed={collapsed}
          active={isSettings}
          onClick={() => {
            if (isSettings) {
              safeNavigate(lastNonSettingsPathRef.current || '/guid');
              return;
            }
            safeNavigate('/settings/hivemind');
          }}
        />
      </div>
    </div>
  );
};

export default NexusSidebar;
