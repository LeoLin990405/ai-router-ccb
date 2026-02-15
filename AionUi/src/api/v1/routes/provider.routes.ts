/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import {
  providerSchema,
  createProviderRequestSchema,
  updateProviderRequestSchema,
} from '../schemas/model';
import { paginationQuerySchema } from '../schemas/common';
import { validateRequest } from '../middleware/validate';
import { authenticateJWT } from '../middleware/auth';

const router = Router();

// All provider routes require authentication
router.use(authenticateJWT);

/**
 * GET /api/v1/providers
 * List all providers with pagination
 */
router.get(
  '/',
  validateRequest({
    query: paginationQuerySchema.extend({
      type: z.enum(['openai', 'anthropic', 'google', 'custom']).optional(),
      enabled: z.coerce.boolean().optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { page, pageSize, type, enabled } = req.query as any;

      // TODO: Fetch from database
      // const providers = await providerService.list({ type, enabled }, page, pageSize)

      // Mock data
      const mockProviders = [
        {
          id: crypto.randomUUID(),
          name: 'Google AI',
          type: 'google' as const,
          apiKey: '***masked***',
          baseUrl: 'https://generativelanguage.googleapis.com',
          enabled: true,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          id: crypto.randomUUID(),
          name: 'Anthropic',
          type: 'anthropic' as const,
          apiKey: '***masked***',
          baseUrl: 'https://api.anthropic.com',
          enabled: true,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          id: crypto.randomUUID(),
          name: 'OpenAI',
          type: 'openai' as const,
          apiKey: '***masked***',
          baseUrl: 'https://api.openai.com',
          enabled: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ];

      const totalItems = mockProviders.length;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: mockProviders,
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
 * POST /api/v1/providers
 * Create new provider
 */
router.post(
  '/',
  validateRequest({ body: createProviderRequestSchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const data = req.body as z.infer<typeof createProviderRequestSchema>;

      // TODO: Create in database (hash/encrypt API key)
      // const provider = await providerService.create(data)

      // Mock response (mask API key)
      const provider = {
        id: crypto.randomUUID(),
        ...data,
        apiKey: data.apiKey ? '***masked***' : undefined,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.status(201).json({
        success: true,
        data: provider,
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
 * GET /api/v1/providers/:id
 * Get single provider
 */
router.get(
  '/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Fetch from database
      // const provider = await providerService.getById(id)

      // Mock data
      const provider = {
        id,
        name: 'Google AI',
        type: 'google' as const,
        apiKey: '***masked***',
        baseUrl: 'https://generativelanguage.googleapis.com',
        enabled: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.json({
        success: true,
        data: provider,
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
 * PATCH /api/v1/providers/:id
 * Update provider
 */
router.patch(
  '/:id',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: updateProviderRequestSchema,
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const updates = req.body as z.infer<typeof updateProviderRequestSchema>;

      // TODO: Update in database (hash/encrypt API key if provided)
      // const provider = await providerService.update(id, updates)

      // Mock response
      const provider = {
        id,
        name: updates.name || 'Updated Provider',
        type: 'custom' as const,
        apiKey: updates.apiKey ? '***masked***' : '***masked***',
        baseUrl: updates.baseUrl,
        enabled: updates.enabled ?? true,
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.json({
        success: true,
        data: provider,
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
 * DELETE /api/v1/providers/:id
 * Delete provider
 */
router.delete(
  '/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Delete from database
      // Check if any models are using this provider before deletion
      // await providerService.delete(id)

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
 * POST /api/v1/providers/:id/test
 * Test provider connection
 */
router.post(
  '/:id/test',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Test provider connection
      // const result = await providerService.testConnection(id)

      // Mock response
      const result = {
        providerId: id,
        success: true,
        latency: Math.floor(Math.random() * 500) + 100, // 100-600ms
        modelsAvailable: Math.floor(Math.random() * 10) + 5, // 5-15 models
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
