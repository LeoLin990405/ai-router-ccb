/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type { IAgentTask, IProviderSelection } from './types';

const PROVIDER_ROUTING_RULES: Record<string, IProviderSelection> = {
  frontend: { provider: 'gemini', model: '3f', cost: 0.035 },
  backend: { provider: 'qwen', model: 'coder', cost: 0.008 },
  algorithm: { provider: 'codex', model: 'o3', cost: 0.375 },
  review: { provider: 'codex', model: 'o3', cost: 0.375 },
  chinese: { provider: 'kimi', model: 'thinking', cost: 0.005 },
  quick: { provider: 'kimi', model: 'normal', cost: 0.005 },
  default: { provider: 'claude', model: 'sonnet', cost: 0.09 },
};

const FAILOVER_ORDER: Record<string, Array<{ provider: string; model: string }>> = {
  claude: [
    { provider: 'gemini', model: '3f' },
    { provider: 'qwen', model: 'coder' },
    { provider: 'gateway', model: 'auto' },
  ],
  codex: [
    { provider: 'claude', model: 'sonnet' },
    { provider: 'gemini', model: '3f' },
    { provider: 'gateway', model: 'auto' },
  ],
  gemini: [
    { provider: 'claude', model: 'sonnet' },
    { provider: 'kimi', model: 'thinking' },
    { provider: 'gateway', model: 'auto' },
  ],
  kimi: [
    { provider: 'gemini', model: '3f' },
    { provider: 'claude', model: 'sonnet' },
    { provider: 'gateway', model: 'auto' },
  ],
  qwen: [
    { provider: 'codex', model: 'o3' },
    { provider: 'claude', model: 'sonnet' },
    { provider: 'gateway', model: 'auto' },
  ],
  gateway: [
    { provider: 'kimi', model: 'thinking' },
    { provider: 'qwen', model: 'coder' },
  ],
};

export class ProviderRouter {
  selectProvider(task: IAgentTask): IProviderSelection {
    const metadataText = task.metadata || '{}';
    let metadata: Record<string, unknown> = {};

    try {
      metadata = JSON.parse(metadataText) as Record<string, unknown>;
    } catch {
      metadata = {};
    }

    const skills = Array.isArray(metadata.skills) ? metadata.skills.map((value) => String(value).toLowerCase()) : [];
    const subject = task.subject.toLowerCase();
    const description = task.description.toLowerCase();

    const matchBySkill = this.pickRule(skills);
    if (matchBySkill) {
      return matchBySkill;
    }

    const combined = `${subject} ${description}`;
    if (combined.includes('backend') || combined.includes('api') || combined.includes('database')) {
      return PROVIDER_ROUTING_RULES.backend;
    }
    if (combined.includes('frontend') || combined.includes('react') || /\bui\b/.test(combined)) {
      return PROVIDER_ROUTING_RULES.frontend;
    }
    if (combined.includes('review') || combined.includes('audit') || combined.includes('security')) {
      return PROVIDER_ROUTING_RULES.review;
    }
    if (combined.includes('chinese') || combined.includes('中文') || combined.includes('translation')) {
      return PROVIDER_ROUTING_RULES.chinese;
    }

    return PROVIDER_ROUTING_RULES.default;
  }

  estimateCost(tasks: IAgentTask[], avgTokenPerTask = 12000): number {
    return tasks.reduce((total, task) => {
      const selected = this.selectProvider(task);
      return total + (avgTokenPerTask / 1000) * selected.cost;
    }, 0);
  }

  failover(task: IAgentTask, failedProvider: string): { provider: string; model: string } {
    const candidates = FAILOVER_ORDER[failedProvider] || [];
    if (candidates.length > 0) {
      return candidates[0];
    }

    const fallback = this.selectProvider(task);
    return { provider: fallback.provider, model: fallback.model };
  }

  /**
   * Delegate provider selection to the Gateway's smart routing.
   * Returns a gateway provider selection that lets the Gateway API decide the best provider.
   */
  selectViaGateway(_task: IAgentTask): IProviderSelection {
    return { provider: 'gateway', model: 'auto', cost: 0.01 };
  }

  private pickRule(skills: string[]): IProviderSelection | null {
    for (const skill of skills) {
      if (PROVIDER_ROUTING_RULES[skill]) {
        return PROVIDER_ROUTING_RULES[skill];
      }
    }
    return null;
  }
}

export const providerRouter = new ProviderRouter();
