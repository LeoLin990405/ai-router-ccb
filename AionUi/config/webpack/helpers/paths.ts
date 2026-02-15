import path from 'path';

export const ROOT_DIR = path.resolve(__dirname, '../../../');
export const SRC_DIR = path.resolve(ROOT_DIR, 'src');
export const RENDERER_DIR = path.resolve(SRC_DIR, 'renderer');
export const PROCESS_DIR = path.resolve(SRC_DIR, 'process');
export const WORKER_DIR = path.resolve(SRC_DIR, 'worker');
export const COMMON_DIR = path.resolve(SRC_DIR, 'common');
export const PUBLIC_DIR = path.resolve(ROOT_DIR, 'public');
export const DIST_DIR = path.resolve(ROOT_DIR, '.webpack');

export const isDevelopment = process.env.NODE_ENV !== 'production';
