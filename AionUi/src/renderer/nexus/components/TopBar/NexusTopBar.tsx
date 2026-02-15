/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { MenuFold, MenuUnfold } from '@icon-park/react';
import { Bell, PanelRightClose, PanelRightOpen, SearchCode } from 'lucide-react';
import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import NexusCommandInput from '../CommandInput/NexusCommandInput';

interface NexusTopBarProps {
  collapsed: boolean;
  onToggleSidebar: () => void;
  onToggleInspector: () => void;
  inspectorOpen: boolean;
}

const routeTitleMap: Record<string, string> = {
  '/guid': 'Command Center',
  '/knowledge': 'Knowledge Hub',
  '/monitor': 'Observability',
  '/memory': 'Memory Hub',
  '/agent-teams': 'Agent Teams',
  '/skills': 'Skills Manager',
  '/settings': 'System Settings',
};

const NexusTopBar: React.FC<NexusTopBarProps> = ({ collapsed, onToggleSidebar, onToggleInspector, inspectorOpen }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const safeNavigate = (target: string) => {
    void Promise.resolve(navigate(target)).catch((error) => {
      console.error('Navigation failed:', error);
    });
  };

  const matchedPrefix = Object.keys(routeTitleMap).find((prefix) => location.pathname.startsWith(prefix));
  const title = matchedPrefix ? routeTitleMap[matchedPrefix] : 'HiveMind Nexus';

  return (
    <header className='nexus-topbar flex items-center gap-10px px-12px shrink-0'>
      <button type='button' className='app-titlebar__button' onClick={onToggleSidebar} aria-label='Toggle sidebar'>
        {collapsed ? <MenuUnfold theme='outline' size='18' fill='currentColor' /> : <MenuFold theme='outline' size='18' fill='currentColor' />}
      </button>

      <div className='min-w-180px'>
        <div className='nexus-topbar__title'>{title}</div>
        <div className='nexus-topbar__meta'>Nexus • Parallel Orchestration</div>
      </div>

      <div className='flex-1 max-w-700px'>
        <NexusCommandInput
          onSubmit={(command) => {
            if (command.startsWith('/goto ')) {
              safeNavigate(command.replace('/goto ', '').trim() || '/guid');
              return;
            }
            if (command.startsWith('/monitor')) {
              safeNavigate('/monitor');
              return;
            }
            safeNavigate('/guid');
          }}
        />
      </div>

      <div className='hidden lg:flex items-center gap-8px px-10px py-6px rounded-[999px] border border-[var(--nexus-border-subtle)] bg-[rgba(18,23,34,0.88)]'>
        <span className='nexus-status-dot nexus-status-dot--ok' />
        <span className='text-11px text-[var(--nexus-text-secondary)]'>Gateway Healthy</span>
      </div>

      <button type='button' className='app-titlebar__button' onClick={() => safeNavigate('/monitor')} aria-label='Open monitor'>
        <SearchCode size={16} />
      </button>
      <button type='button' className='app-titlebar__button' onClick={onToggleInspector} aria-label='Toggle inspector'>
        {inspectorOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
      </button>
      <button type='button' className='app-titlebar__button' onClick={() => safeNavigate('/settings/hivemind')} aria-label='Open notifications'>
        <Bell size={16} />
      </button>
    </header>
  );
};

export default NexusTopBar;
