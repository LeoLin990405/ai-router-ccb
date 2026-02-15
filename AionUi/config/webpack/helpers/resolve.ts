import path from 'path';
import { ROOT_DIR, SRC_DIR, RENDERER_DIR, PROCESS_DIR, WORKER_DIR, COMMON_DIR } from './paths';

export const createResolveConfig = (extensions: string[] = []) => ({
  extensions: ['.js', '.ts', '.jsx', '.tsx', '.json', ...extensions],
  alias: {
    '@': SRC_DIR,
    '@common': COMMON_DIR,
    '@renderer': RENDERER_DIR,
    '@process': PROCESS_DIR,
    '@worker': WORKER_DIR,
  },
});
