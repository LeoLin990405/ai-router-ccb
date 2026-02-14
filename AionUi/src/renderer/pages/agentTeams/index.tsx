/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/renderer/components/ui/button';
import { useTranslation } from 'react-i18next';

const NAV_ITEMS = [
  { key: '/agent-teams/dashboard', i18nKey: 'agentTeams.dashboard', fallback: 'Dashboard' },
  { key: '/agent-teams/teams', i18nKey: 'agentTeams.teams', fallback: 'Teams' },
  { key: '/agent-teams/tasks', i18nKey: 'agentTeams.tasks', fallback: 'Tasks' },
  { key: '/agent-teams/monitor', i18nKey: 'agentTeams.monitor', fallback: 'Monitor' },
  { key: '/agent-teams/analytics', i18nKey: 'agentTeams.analytics', fallback: 'Analytics' },
];

const AgentTeamsLayout: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className='size-full flex flex-col bg-1 p-24px overflow-hidden'>
      <div className='mb-16px'>
        <h1 className='text-2xl font-semibold mb-2'>
          {t('agentTeams.title', { defaultValue: 'Agent Teams' })}
        </h1>
        <p className='text-muted-foreground text-sm mb-0'>
          {t('agentTeams.subtitle', { defaultValue: 'Distributed AI collaboration dashboard.' })}
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname.startsWith(item.key);
          return (
            <Button
              key={item.key}
              variant={isActive ? 'default' : 'outline'}
              onClick={() => {
                void navigate(item.key);
              }}
            >
              {t(item.i18nKey, { defaultValue: item.fallback })}
            </Button>
          );
        })}
      </div>

      <div className='flex-1 min-h-0 overflow-auto'>
        <Outlet />
      </div>
    </div>
  );
};

export default AgentTeamsLayout;
