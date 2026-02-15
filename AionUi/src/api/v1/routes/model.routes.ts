/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import {
  modelSchema,
  createModelRequestSchema,
  updateModelRequestSchema,
} from '../schemas/model';
import { paginationQuerySchema } from '../schemas/common';
import { validateRequest } from '../middleware/validate';
import { authenticateJWT } from '../middleware/auth';

const router = Router();

// All model routes require authentication
router.use(authenticateJWT);

/**
 * GET /api/v1/models
 * List all models with pagination
 */
router.get(
  '/',
  validateRequest({
    query: paginationQuerySchema.extend({
      providerId: z.string().uuid().optional(),
      enabled: z.coerce.boolean().optional(),
      capability: z.enum(['chat', 'vision', 'functionCalling', 'streaming']).optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { page, pageSize, providerId, enabled, capability } = req.query as any;

      // TODO: Fetch from database
      // const models = await modelService.list({ providerId, enabled, capability }, page, pageSize)

      // Mock data
      const mockModels = [
        {
          id: crypto.randomUUID(),
          name: 'gemini-2.0-flash',
          displayName: 'Gemini 2.0 Flash',
          providerId: crypto.randomUUID(),
          modelId: 'gemini-2.0-flash-exp',
          capabilities: {
            chat: true,
            vision: true,
            functionCalling: true,
            streaming: true,
          },
          contextWindow: 1000000,
          maxOutputTokens: 8192,
          enabled: true,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          id: crypto.randomUUID(),
          name: 'claude-sonnet-4.5',
          displayName: 'Claude Sonnet 4.5',
          providerId: crypto.randomUUID(),
          modelId: 'claude-sonnet-4-5-20250929',
          capabilities: {
            chat: true,
            vision: true,
            functionCalling: true,
            streaming: true,
          },
          contextWindow: 200000,
          maxOutputTokens: 8192,
          enabled: true,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ];

      const totalItems = mockModels.length;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: mockModels,
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
 * POST /api/v1/models
 * Create new model
 */
router.post(
  '/',
  validateRequest({ body: createModelRequestSchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const data = req.body as z.infer<typeof createModelRequestSchema>;

      // TODO: Create in database
      // const model = await modelService.create(data)

      // Mock response
      const model = {
        id: crypto.randomUUID(),
        ...data,
        capabilities: data.capabilities || {
          chat: true,
          vision: false,
          functionCalling: false,
          streaming: true,
        },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.status(201).json({
        success: true,
        data: model,
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
 * GET /api/v1/models/:id
 * Get single model
 */
router.get(
  '/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Fetch from database
      // const model = await modelService.getById(id)

      // Mock data
      const model = {
        id,
        name: 'gemini-2.0-flash',
        displayName: 'Gemini 2.0 Flash',
        providerId: crypto.randomUUID(),
        modelId: 'gemini-2.0-flash-exp',
        capabilities: {
          chat: true,
          vision: true,
          functionCalling: true,
          streaming: true,
        },
        contextWindow: 1000000,
        maxOutputTokens: 8192,
        enabled: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.json({
        success: true,
        data: model,
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
 * PATCH /api/v1/models/:id
 * Update model
 */
router.patch(
  '/:id',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: updateModelRequestSchema,
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const updates = req.body as z.infer<typeof updateModelRequestSchema>;

      // TODO: Update in database
      // const model = await modelService.update(id, updates)

      // Mock response
      const model = {
        id,
        name: updates.name || 'updated-model',
        displayName: updates.displayName || 'Updated Model',
        providerId: crypto.randomUUID(),
        modelId: updates.modelId || 'model-id',
        capabilities: updates.capabilities || {
          chat: true,
          vision: false,
          functionCalling: false,
          streaming: true,
        },
        contextWindow: updates.contextWindow,
        maxOutputTokens: updates.maxOutputTokens,
        enabled: updates.enabled ?? true,
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.json({
        success: true,
        data: model,
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
 * DELETE /api/v1/models/:id
 * Delete model
 */
router.delete(
  '/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Delete from database
      // await modelService.delete(id)

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
 * POST /api/v1/models/:id/test
 * Test model connection
 */
router.post(
  '/:id/test',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: z.object({
      prompt: z.string().default('Hello, this is a test message.'),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { prompt } = req.body;

      // TODO: Test model via provider
      // const result = await modelService.test(id, prompt)

      // Mock response
      const result = {
        modelId: id,
        success: true,
        prompt,
        response: 'Hello! I received your test message successfully.',
        latency: Math.floor(Math.random() * 1000) + 200, // 200-1200ms
        testedAt: new Date().toISOString(),
      };

      res.json({
        success: true,
        data: result,
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
