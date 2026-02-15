/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Activity, ArrowUpRight, ChartNoAxesCombined, Cpu, WalletCards } from 'lucide-react';
import React from 'react';
import { useNavigate } from 'react-router-dom';

type ProviderState = 'ok' | 'warn' | 'err';

interface ProviderMetric {
  name: string;
  latency: string;
  state: ProviderState;
}

const providerMetrics: ProviderMetric[] = [
  { name: 'Claude', latency: '1.2s', state: 'ok' },
  { name: 'Codex', latency: '1.7s', state: 'ok' },
  { name: 'Gemini', latency: '2.1s', state: 'warn' },
  { name: 'Qwen', latency: '1.4s', state: 'ok' },
  { name: 'DeepSeek', latency: '2.8s', state: 'warn' },
  { name: 'Ollama', latency: 'offline', state: 'err' },
];

const stateClassMap: Record<ProviderState, string> = {
  ok: 'nexus-chip nexus-chip--ok',
  warn: 'nexus-chip nexus-chip--warn',
  err: 'nexus-chip nexus-chip--err',
};

const stateTextMap: Record<ProviderState, string> = {
  ok: 'healthy',
  warn: 'degraded',
  err: 'down',
};

const NexusRightRail: React.FC = () => {
  const navigate = useNavigate();

  return (
    <aside className='nexus-right-rail'>
      <div className='nexus-rail-head'>
        <div>
          <div className='nexus-rail-title'>Control Telemetry</div>
          <div className='nexus-rail-subtitle'>Live provider status stream</div>
        </div>
      </div>

      <div className='nexus-rail-scroll'>
        <section className='nexus-rail-card'>
          <div className='nexus-rail-card__title'>Provider Health</div>
          {providerMetrics.map((provider) => (
            <div key={provider.name} className='nexus-provider-row'>
              <div className='nexus-provider-left'>
                <span className={`nexus-status-dot nexus-status-dot--${provider.state === 'ok' ? 'ok' : provider.state === 'warn' ? 'warn' : 'err'}`} />
                <span>{provider.name}</span>
              </div>
              <div className='flex items-center gap-8px'>
                <span className='nexus-provider-latency'>{provider.latency}</span>
                <span className={stateClassMap[provider.state]}>{stateTextMap[provider.state]}</span>
              </div>
            </div>
          ))}
        </section>

        <section className='nexus-rail-card'>
          <div className='nexus-rail-card__title'>Quick Access</div>
          <div className='flex flex-col gap-8px'>
            <button type='button' className='nexus-quick-btn' onClick={() => navigate('/monitor')}>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-8px'>
                  <Activity size={13} />
                  Runtime Monitor
                </span>
                <ArrowUpRight size={12} />
              </div>
            </button>
            <button type='button' className='nexus-quick-btn' onClick={() => navigate('/monitor/stats')}>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-8px'>
                  <ChartNoAxesCombined size={13} />
                  Cost & Tokens
                </span>
                <ArrowUpRight size={12} />
              </div>
            </button>
            <button type='button' className='nexus-quick-btn' onClick={() => navigate('/settings/model')}>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-8px'>
                  <Cpu size={13} />
                  Model Routing
                </span>
                <ArrowUpRight size={12} />
              </div>
            </button>
            <button type='button' className='nexus-quick-btn' onClick={() => navigate('/skills')}>
              <div className='flex items-center justify-between'>
                <span className='flex items-center gap-8px'>
                  <WalletCards size={13} />
                  Skills Manager
                </span>
                <ArrowUpRight size={12} />
              </div>
            </button>
          </div>
        </section>
      </div>
    </aside>
  );
};

export default NexusRightRail;
