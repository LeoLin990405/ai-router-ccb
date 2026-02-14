/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from 'fs/promises';
import path from 'path';

export class SymlinkManager {
  async isSymlink(targetPath: string): Promise<boolean> {
    try {
      const stats = await fs.lstat(targetPath);
      return stats.isSymbolicLink();
    } catch {
      return false;
    }
  }

  async createSymlink(sourcePath: string, targetPath: string): Promise<void> {
    await fs.mkdir(path.dirname(targetPath), { recursive: true });

    try {
      await fs.rm(targetPath, { recursive: true, force: true });
    } catch {
      // ignore
    }

    await fs.symlink(sourcePath, targetPath, 'junction');
  }

  async removeSymlink(targetPath: string): Promise<void> {
    try {
      const stats = await fs.lstat(targetPath);
      if (stats.isSymbolicLink() || stats.isFile()) {
        await fs.unlink(targetPath);
        return;
      }

      await fs.rm(targetPath, { recursive: true, force: true });
    } catch {
      // ignore
    }
  }
}
