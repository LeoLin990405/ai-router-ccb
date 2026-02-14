/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import os from 'os';
import path from 'path';

export const expandHome = (inputPath: string): string => {
  if (!inputPath) {
    return inputPath;
  }

  if (inputPath === '~') {
    return os.homedir();
  }

  if (inputPath.startsWith('~/')) {
    return path.join(os.homedir(), inputPath.slice(2));
  }

  return inputPath;
};

export const getSkillsRootPath = (): string => {
  return expandHome('~/.local/share/hivemind/skills');
};
