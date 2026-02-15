/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { ConfigStorage } from '@/common/storage';
import PwaPullToRefresh from '@/renderer/components/PwaPullToRefresh';
import Titlebar from '@/renderer/components/Titlebar';
import UpdateModal from '@/renderer/components/UpdateModal';
import { LayoutContext } from '@/renderer/context/LayoutContext';
import { useDirectorySelection } from '@/renderer/hooks/useDirectorySelection';
import { useMultiAgentDetection } from '@/renderer/hooks/useMultiAgentDetection';
import { processCustomCss } from '@/renderer/utils/customCssProcessor';
import classNames from 'classnames';
import React, { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import NexusRightRail from '../components/RightRail/NexusRightRail';
import NexusTopBar from '../components/TopBar/NexusTopBar';

const DEFAULT_SIDER_WIDTH = 258;

const NexusLayout: React.FC<{ sider: React.ReactNode }> = ({ sider }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [customCss, setCustomCss] = useState<string>('');
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const { contextHolder: multiAgentContextHolder } = useMultiAgentDetection();
  const { contextHolder: directorySelectionContextHolder } = useDirectorySelection();
  const location = useLocation();
  const workspaceAvailable = location.pathname.startsWith('/conversation/');
  const collapsedRef = useRef(collapsed);

  useEffect(() => {
    const loadCustomCss = () => {
      ConfigStorage.get('customCss')
        .then((css) => setCustomCss(css || ''))
        .catch((error) => {
          console.error('Failed to load custom CSS:', error);
        });
    };

    loadCustomCss();

    const handleCssUpdate = (event: CustomEvent) => {
      if (event.detail?.customCss !== undefined) {
        setCustomCss(event.detail.customCss || '');
      }
    };

    window.addEventListener('custom-css-updated', handleCssUpdate as EventListener);
    return () => {
      window.removeEventListener('custom-css-updated', handleCssUpdate as EventListener);
    };
  }, []);

  useEffect(() => {
    const styleId = 'user-defined-custom-css';

    if (!customCss) {
      document.getElementById(styleId)?.remove();
      return;
    }

    const wrappedCss = processCustomCss(customCss);
    const styleEl = document.createElement('style');
    styleEl.id = styleId;
    styleEl.type = 'text/css';
    styleEl.textContent = wrappedCss;

    document.getElementById(styleId)?.remove();
    document.head.appendChild(styleEl);

    return () => {
      document.getElementById(styleId)?.remove();
    };
  }, [customCss]);

  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 960;
      setIsMobile(mobile);
      if (mobile) {
        setInspectorOpen(false);
      }
    };

    checkMobile();

    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    if (!isMobile || collapsedRef.current) {
      return;
    }
    setCollapsed(true);
  }, [isMobile]);

  useEffect(() => {
    collapsedRef.current = collapsed;
  }, [collapsed]);

  const siderWidth = isMobile ? (collapsed ? 0 : DEFAULT_SIDER_WIDTH) : collapsed ? 72 : DEFAULT_SIDER_WIDTH;

  return (
    <LayoutContext.Provider value={{ isMobile, siderCollapsed: collapsed, setSiderCollapsed: setCollapsed }}>
      <div className='nexus-shell flex flex-col size-full min-h-0'>
        <Titlebar workspaceAvailable={workspaceAvailable} />

        <div className='nexus-workspace flex size-full flex-1 min-h-0'>
          <aside
            className={classNames('nexus-sider flex flex-col shrink-0 transition-all duration-200', {
              collapsed,
            })}
            style={{
              width: siderWidth,
              ...(isMobile
                ? {
                    position: 'fixed',
                    left: 0,
                    top: 40,
                    bottom: 0,
                    zIndex: 120,
                    transform: collapsed ? 'translateX(-100%)' : 'translateX(0)',
                    transition: 'transform 160ms ease',
                  }
                : {}),
            }}
          >
            <header className='nexus-sider-header flex items-center gap-10px shrink-0'>
              <span className='nexus-status-dot nexus-status-dot--ok' />
              {!collapsed && (
                <div className='flex flex-col'>
                  <span className='nexus-brand-text'>HiveMind Nexus</span>
                  <span className='nexus-sider-kicker'>AI Command Console</span>
                </div>
              )}
            </header>
            <div className='p-8px flex-1 min-h-0 overflow-auto'>
              {React.isValidElement(sider)
                ? React.cloneElement(sider, {
                    onSessionClick: () => {
                      if (isMobile) {
                        setCollapsed(true);
                      }
                    },
                    collapsed,
                  } as any)
                : sider}
            </div>
          </aside>

          {isMobile && !collapsed && <div className='fixed inset-0 bg-[rgba(6,8,14,0.66)] z-110' onClick={() => setCollapsed(true)} aria-hidden='true' />}

          <section className='nexus-main flex flex-col flex-1 min-h-0'>
            <NexusTopBar collapsed={collapsed} onToggleSidebar={() => setCollapsed((prev) => !prev)} onToggleInspector={() => setInspectorOpen((prev) => !prev)} inspectorOpen={inspectorOpen} />
            <main className='nexus-content flex-1 min-h-0 overflow-auto'>
              <Outlet />
              {multiAgentContextHolder}
              {directorySelectionContextHolder}
              <PwaPullToRefresh />
              <UpdateModal />
            </main>
          </section>

          {!isMobile && inspectorOpen && <NexusRightRail />}

          {isMobile && inspectorOpen && (
            <>
              <div className='fixed inset-0 bg-[rgba(6,8,14,0.66)] z-125' onClick={() => setInspectorOpen(false)} aria-hidden='true' />
              <div className='fixed right-0 top-40px bottom-0 z-130'>
                <NexusRightRail />
              </div>
            </>
          )}
        </div>
      </div>
    </LayoutContext.Provider>
  );
};

export default NexusLayout;
