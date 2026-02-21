/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type { IAgentProvider } from './types';
import { ClaudeProvider } from './ClaudeProvider';
import { GeminiProvider } from './GeminiProvider';
import { KimiProvider } from './KimiProvider';
import { QwenProvider } from './QwenProvider';
import { CCBProvider } from './CCBProvider';
import { GatewayProvider } from './GatewayProvider';

export class ProviderFactory {
  create(provider: string, model: string): IAgentProvider {
    switch (provider) {
      case 'claude':
        return new ClaudeProvider(model || 'sonnet');
      case 'gemini':
        return new GeminiProvider(model || '3f');
      case 'kimi':
        return new KimiProvider(model || 'thinking');
      case 'qwen':
        return new QwenProvider(model || 'coder');
      case 'gateway':
        return new GatewayProvider(provider, model || 'auto');
      default:
        return new CCBProvider(provider, model || 'default');
    }
  }
}

export const providerFactory = new ProviderFactory();
