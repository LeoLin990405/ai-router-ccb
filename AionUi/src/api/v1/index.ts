/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Router } from 'express';
import authRoutes from './routes/auth.routes';
import conversationRoutes from './routes/conversation.routes';
import messageRoutes from './routes/message.routes';
import fileRoutes from './routes/file.routes';
import modelRoutes from './routes/model.routes';
import providerRoutes from './routes/provider.routes';
import geminiRoutes from './routes/gemini.routes';
import codexRoutes from './routes/codex.routes';
import acpRoutes from './routes/acp.routes';
import mcpRoutes from './routes/mcp.routes';
// Import other routes as they are implemented
// import skillsRoutes from './routes/skills.routes';
// import cronRoutes from './routes/cron.routes';
// import systemRoutes from './routes/system.routes';

const router = Router();

/**
 * Mount v1 API routes
 */
router.use('/auth', authRoutes);
router.use('/conversations', conversationRoutes);
router.use('/messages', messageRoutes);
router.use('/files', fileRoutes);
router.use('/models', modelRoutes);
router.use('/providers', providerRoutes);
router.use('/gemini', geminiRoutes);
router.use('/codex', codexRoutes);
router.use('/acp', acpRoutes);
router.use('/mcp', mcpRoutes);
// router.use('/skills', skillsRoutes);
// router.use('/cron', cronRoutes);
// router.use('/system', systemRoutes);

/**
 * Health check endpoint (no auth required)
 */
router.get('/health', (_req, res) => {
  res.json({
    success: true,
    data: {
      status: 'healthy',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
    },
    meta: {
      timestamp: new Date().toISOString(),
      requestId: crypto.randomUUID(),
    },
  });
});

export default router;
