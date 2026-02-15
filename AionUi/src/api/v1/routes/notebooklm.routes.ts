/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { paginationQuerySchema } from '../schemas/common';
import { validateRequest } from '../middleware/validate';
import { authenticateJWT } from '../middleware/auth';

const router = Router();

// All NotebookLM routes require authentication
router.use(authenticateJWT);

/**
 * GET /api/v1/notebooklm/notebooks
 * List all NotebookLM notebooks
 */
router.get(
  '/notebooks',
  validateRequest({
    query: paginationQuerySchema.extend({
      search: z.string().optional(),
      sortBy: z.enum(['created', 'updated', 'title']).default('updated'),
      sortOrder: z.enum(['asc', 'desc']).default('desc'),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { page, pageSize, search, sortBy, sortOrder } = req.query as any;

      // TODO: Fetch from NotebookLM API
      // const notebooks = await notebooklmService.listNotebooks({ search, sortBy, sortOrder }, page, pageSize)

      // Mock data
      const mockNotebooks = [
        {
          id: crypto.randomUUID(),
          title: 'AI Research Papers 2025',
          description: 'Collection of latest AI/ML research papers',
          sourceCount: 42,
          lastModified: new Date(Date.now() - 3600000).toISOString(),
          createdAt: new Date(Date.now() - 2592000000).toISOString(),
          url: 'https://notebooklm.google.com/notebook/abc123',
        },
        {
          id: crypto.randomUUID(),
          title: 'Product Documentation',
          description: 'Internal product docs and specifications',
          sourceCount: 28,
          lastModified: new Date(Date.now() - 7200000).toISOString(),
          createdAt: new Date(Date.now() - 5184000000).toISOString(),
          url: 'https://notebooklm.google.com/notebook/def456',
        },
      ];

      const totalItems = mockNotebooks.length;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: mockNotebooks,
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
 * POST /api/v1/notebooklm/notebooks
 * Create new NotebookLM notebook
 */
router.post(
  '/notebooks',
  validateRequest({
    body: z.object({
      title: z.string().min(1).max(200),
      description: z.string().optional(),
      sources: z
        .array(
          z.union([
            z.object({ type: z.literal('url'), url: z.string().url() }),
            z.object({ type: z.literal('file'), path: z.string() }),
            z.object({ type: z.literal('text'), content: z.string() }),
          ])
        )
        .optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { title, description, sources } = req.body;

      // TODO: Create notebook via NotebookLM API
      // const notebook = await notebooklmService.createNotebook({ title, description, sources })

      // Mock response
      const notebook = {
        id: crypto.randomUUID(),
        title,
        description,
        sourceCount: sources?.length || 0,
        lastModified: new Date().toISOString(),
        createdAt: new Date().toISOString(),
        url: `https://notebooklm.google.com/notebook/${crypto.randomUUID()}`,
      };

      res.status(201).json({
        success: true,
        data: notebook,
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
 * POST /api/v1/notebooklm/notebooks/:id/sources
 * Add sources to notebook
 */
router.post(
  '/notebooks/:id/sources',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: z.object({
      sources: z.array(
        z.union([
          z.object({ type: z.literal('url'), url: z.string().url() }),
          z.object({ type: z.literal('file'), path: z.string() }),
          z.object({ type: z.literal('text'), content: z.string(), title: z.string().optional() }),
          z.object({
            type: z.literal('conversation'),
            conversationId: z.string().uuid(),
          }),
        ])
      ),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { sources } = req.body;

      // TODO: Add sources via NotebookLM API
      // const result = await notebooklmService.addSources(id, sources)

      // Mock response
      const result = {
        notebookId: id,
        sourcesAdded: sources.length,
        sources: sources.map((source) => ({
          id: crypto.randomUUID(),
          ...source,
          addedAt: new Date().toISOString(),
        })),
      };

      res.status(201).json({
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

/**
 * POST /api/v1/notebooklm/notebooks/:id/query
 * Query notebook using NotebookLM
 */
router.post(
  '/notebooks/:id/query',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: z.object({
      question: z.string().min(1),
      context: z.string().optional(),
      includeSourceCitations: z.boolean().default(true),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { question, context, includeSourceCitations } = req.body;

      // TODO: Query via NotebookLM API
      // const result = await notebooklmService.query(id, { question, context, includeSourceCitations })

      // Mock response
      const result = {
        notebookId: id,
        question,
        answer:
          'Based on the sources in your notebook, here is a comprehensive answer to your question...',
        citations: includeSourceCitations
          ? [
              {
                sourceId: crypto.randomUUID(),
                sourceTitle: 'AI Research Paper #1',
                excerpt: 'Relevant excerpt from the source...',
                relevanceScore: 0.92,
              },
              {
                sourceId: crypto.randomUUID(),
                sourceTitle: 'Technical Documentation',
                excerpt: 'Another relevant excerpt...',
                relevanceScore: 0.87,
              },
            ]
          : undefined,
        confidence: 0.89,
        queriedAt: new Date().toISOString(),
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

/**
 * POST /api/v1/notebooklm/notebooks/:id/generate
 * Generate content from notebook (study guide, FAQ, etc.)
 */
router.post(
  '/notebooks/:id/generate',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: z.object({
      type: z.enum(['study_guide', 'faq', 'summary', 'briefing_doc', 'timeline']),
      options: z
        .object({
          detailLevel: z.enum(['brief', 'standard', 'detailed']).optional(),
          includeSourceRefs: z.boolean().optional(),
        })
        .optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { type, options } = req.body;

      // TODO: Generate via NotebookLM API
      // const result = await notebooklmService.generate(id, { type, options })

      // Mock response
      const result = {
        notebookId: id,
        type,
        content: `# Generated ${type.replace('_', ' ')}\n\nThis is the generated content based on your notebook sources...`,
        generatedAt: new Date().toISOString(),
        sourceCount: 15,
        wordCount: 2500,
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
