/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Button, Space, Typography } from '@arco-design/web-react';
import { useTranslation } from 'react-i18next';

const { Title, Paragraph } = Typography;

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
        <Title heading={3} style={{ marginBottom: 8 }}>
          {t('agentTeams.title', { defaultValue: 'Agent Teams' })}
        </Title>
        <Paragraph style={{ marginBottom: 0 }} type='secondary'>
          {t('agentTeams.subtitle', { defaultValue: 'Distributed AI collaboration dashboard.' })}
        </Paragraph>
      </div>

      <Space wrap style={{ marginBottom: 16 }}>
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname.startsWith(item.key);
          return (
            <Button
              key={item.key}
              type={isActive ? 'primary' : 'default'}
              onClick={() => {
                void navigate(item.key);
              }}
            >
              {t(item.i18nKey, { defaultValue: item.fallback })}
            </Button>
          );
        })}
      </Space>

      <div className='flex-1 min-h-0 overflow-auto'>
        <Outlet />
      </div>
    </div>
  );
};

export default AgentTeamsLayout;
