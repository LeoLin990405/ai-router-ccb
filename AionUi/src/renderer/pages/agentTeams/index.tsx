/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/renderer/components/ui/button';
import { useTranslation } from 'react-i18next';
import classNames from 'classnames';

const NAV_ITEMS = [
  { key: '/agent-teams/dashboard', i18nKey: 'agentTeams.dashboard', fallback: 'Dashboard' },
  { key: '/agent-teams/teams', i18nKey: 'agentTeams.teams', fallback: 'Teams' },
  { key: '/agent-teams/tasks', i18nKey: 'agentTeams.tasks', fallback: 'Tasks' },
  { key: '/agent-teams/chat', i18nKey: 'agentTeams.chat', fallback: 'Chat' },
  { key: '/agent-teams/monitor', i18nKey: 'agentTeams.monitor', fallback: 'Team Monitor' },
  { key: '/agent-teams/analytics', i18nKey: 'agentTeams.analytics', fallback: 'Analytics' },
];

const AgentTeamsLayout: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className='hive-agent-teams-layout size-full flex flex-col overflow-hidden'>
      <div className='hive-agent-teams-layout__header'>
        <h1 className='text-2xl font-semibold mb-2'>{t('agentTeams.title', { defaultValue: 'Agent Teams' })}</h1>
        <p className='text-muted-foreground text-sm mb-0'>{t('agentTeams.subtitle', { defaultValue: 'Distributed AI collaboration dashboard.' })}</p>
      </div>

      <div className='hive-agent-teams-layout__nav flex flex-wrap gap-2'>
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname.startsWith(item.key);
          return (
            <Button
              key={item.key}
              variant={isActive ? 'default' : 'outline'}
              className={classNames('hive-agent-teams-layout__nav-item', {
                'hive-agent-teams-layout__nav-item--active': isActive,
              })}
              onClick={() => {
                void navigate(item.key);
              }}
            >
              {t(item.i18nKey, { defaultValue: item.fallback })}
            </Button>
          );
        })}
      </div>

      <div className='hive-agent-teams-layout__content flex-1 min-h-0 overflow-auto'>
        <Outlet />
      </div>
    </div>
  );
};

export default AgentTeamsLayout;
