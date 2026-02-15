/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import {
  conversationSchema,
  createConversationRequestSchema,
  updateConversationRequestSchema,
  listConversationsQuerySchema,
  sendMessageRequestSchema,
} from '../schemas/conversation';
import { paginationQuerySchema } from '../schemas/common';
import { validateRequest } from '../middleware/validate';
import { authenticateJWT } from '../middleware/auth';

const router = Router();

// All conversation routes require authentication
router.use(authenticateJWT);

/**
 * GET /api/v1/conversations
 * List all conversations with pagination
 */
router.get(
  '/',
  validateRequest({ query: listConversationsQuerySchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const query = req.query as z.infer<typeof listConversationsQuerySchema>;
      const { page, pageSize, platform, search, sortBy, sortOrder } = query;

      // TODO: Fetch from database
      // const conversations = await conversationService.list(...)

      // Mock data
      const mockConversations = [
        {
          id: crypto.randomUUID(),
          name: 'Example Conversation',
          platform: 'gemini' as const,
          model: 'gemini-2.0-flash-exp',
          provider: 'google',
          workspace: '/Users/example/projects',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messageCount: 5,
        },
      ];

      const totalItems = 1;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: mockConversations,
        pagination: {
          page,
          pageSize,
          totalPages,
          totalItems,
          hasNext: page < totalPages,
          hasPrev: page > 1,
        },
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * POST /api/v1/conversations
 * Create new conversation
 */
router.post(
  '/',
  validateRequest({ body: createConversationRequestSchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const data = req.body as z.infer<typeof createConversationRequestSchema>;

      // TODO: Create in database
      // const conversation = await conversationService.create(data)

      // Mock response
      const conversation = {
        id: crypto.randomUUID(),
        ...data,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messageCount: 0,
      };

      res.status(201).json({
        success: true,
        data: conversation,
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /api/v1/conversations/:id
 * Get single conversation
 */
router.get(
  '/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Fetch from database
      // const conversation = await conversationService.getById(id)

      // Mock data
      const conversation = {
        id,
        name: 'Example Conversation',
        platform: 'gemini' as const,
        model: 'gemini-2.0-flash-exp',
        provider: 'google',
        workspace: '/Users/example/projects',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messageCount: 5,
      };

      res.json({
        success: true,
        data: conversation,
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * PATCH /api/v1/conversations/:id
 * Update conversation
 */
router.patch(
  '/:id',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: updateConversationRequestSchema,
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const updates = req.body as z.infer<typeof updateConversationRequestSchema>;

      // TODO: Update in database
      // const conversation = await conversationService.update(id, updates)

      // Mock response
      const conversation = {
        id,
        name: updates.name || 'Updated Conversation',
        platform: 'gemini' as const,
        model: 'gemini-2.0-flash-exp',
        workspace: updates.workspace || '/Users/example/projects',
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        updatedAt: new Date().toISOString(),
        messageCount: 5,
        extra: updates.extra,
      };

      res.json({
        success: true,
        data: conversation,
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * DELETE /api/v1/conversations/:id
 * Delete conversation
 */
router.delete(
  '/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Delete from database
      // await conversationService.delete(id)

      res.json({
        success: true,
        data: { id, deleted: true },
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * POST /api/v1/conversations/:id/reset
 * Reset conversation (delete all messages)
 */
router.post(
  '/:id/reset',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Reset in database
      // await conversationService.reset(id)

      res.json({
        success: true,
        data: { id, reset: true, messageCount: 0 },
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * POST /api/v1/conversations/:id/messages
 * Send message to conversation
 */
router.post(
  '/:id/messages',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: sendMessageRequestSchema,
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const messageData = req.body as z.infer<typeof sendMessageRequestSchema>;

      // TODO: Send message via bridge/service
      // const message = await conversationService.sendMessage(id, messageData)

      // Mock response
      const message = {
        id: crypto.randomUUID(),
        conversationId: id,
        role: messageData.role,
        content: messageData.content,
        createdAt: new Date().toISOString(),
        attachments: messageData.attachments,
      };

      res.status(201).json({
        success: true,
        data: message,
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /api/v1/conversations/:id/messages
 * Get messages from conversation
 */
router.get(
  '/:id/messages',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    query: paginationQuerySchema,
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { page, pageSize } = req.query as z.infer<typeof paginationQuerySchema>;

      // TODO: Fetch from database
      // const messages = await conversationService.getMessages(id, page, pageSize)

      // Mock data
      const messages = [
        {
          id: crypto.randomUUID(),
          conversationId: id,
          role: 'user' as const,
          content: 'Hello, how are you?',
          createdAt: new Date().toISOString(),
        },
        {
          id: crypto.randomUUID(),
          conversationId: id,
          role: 'assistant' as const,
          content: "I'm doing well, thank you! How can I help you today?",
          createdAt: new Date().toISOString(),
        },
      ];

      const totalItems = 2;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: messages,
        pagination: {
          page,
          pageSize,
          totalPages,
          totalItems,
          hasNext: page < totalPages,
          hasPrev: page > 1,
        },
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * POST /api/v1/conversations/:id/stop
 * Stop streaming message
 */
router.post(
  '/:id/stop',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Stop streaming via bridge
      // await conversationService.stopStreaming(id)

      res.json({
        success: true,
        data: { id, stopped: true },
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /api/v1/conversations/:id/workspace
 * Get workspace files for conversation
 */
router.get(
  '/:id/workspace',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    query: z.object({
      path: z.string().optional(),
      search: z.string().optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { path, search } = req.query;

      // TODO: Get workspace files
      // const files = await conversationService.getWorkspaceFiles(id, path, search)

      // Mock data
      const files = [
        {
          path: '/project/src',
          name: 'src',
          type: 'directory' as const,
        },
        {
          path: '/project/README.md',
          name: 'README.md',
          type: 'file' as const,
          size: 1024,
          modifiedAt: new Date().toISOString(),
        },
      ];

      res.json({
        success: true,
        data: files,
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

export default router;
