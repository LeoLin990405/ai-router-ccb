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

// All Obsidian routes require authentication
router.use(authenticateJWT);

/**
 * GET /api/v1/obsidian/vaults
 * List configured Obsidian vaults
 */
router.get(
  '/vaults',
  validateRequest({ query: paginationQuerySchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { page, pageSize } = req.query as any;

      // TODO: Fetch from configuration
      // const vaults = await obsidianService.listVaults(page, pageSize)

      // Mock data
      const mockVaults = [
        {
          id: crypto.randomUUID(),
          name: 'Personal Knowledge Base',
          path: '/Users/user/Documents/Obsidian/Personal',
          noteCount: 1247,
          lastSynced: new Date(Date.now() - 1800000).toISOString(),
          autoSync: true,
          syncInterval: 300000, // 5 minutes
          createdAt: new Date(Date.now() - 31536000000).toISOString(),
        },
        {
          id: crypto.randomUUID(),
          name: 'Work Notes',
          path: '/Users/user/Documents/Obsidian/Work',
          noteCount: 567,
          lastSynced: new Date(Date.now() - 3600000).toISOString(),
          autoSync: true,
          syncInterval: 600000, // 10 minutes
          createdAt: new Date(Date.now() - 15552000000).toISOString(),
        },
      ];

      const totalItems = mockVaults.length;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: mockVaults,
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
 * POST /api/v1/obsidian/vaults
 * Add new Obsidian vault
 */
router.post(
  '/vaults',
  validateRequest({
    body: z.object({
      name: z.string().min(1).max(200),
      path: z.string(),
      autoSync: z.boolean().default(true),
      syncInterval: z.number().int().positive().default(300000), // Default 5 min
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { name, path, autoSync, syncInterval } = req.body;

      // TODO: Add vault and verify path
      // const vault = await obsidianService.addVault({ name, path, autoSync, syncInterval })

      // Mock response
      const vault = {
        id: crypto.randomUUID(),
        name,
        path,
        noteCount: 0, // Will be counted on first sync
        lastSynced: null,
        autoSync,
        syncInterval,
        createdAt: new Date().toISOString(),
      };

      res.status(201).json({
        success: true,
        data: vault,
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
 * GET /api/v1/obsidian/vaults/:id/notes
 * List notes from vault
 */
router.get(
  '/vaults/:id/notes',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    query: paginationQuerySchema.extend({
      search: z.string().optional(),
      tag: z.string().optional(),
      folder: z.string().optional(),
      modifiedSince: z.string().datetime().optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { page, pageSize, search, tag, folder, modifiedSince } = req.query as any;

      // TODO: Fetch notes from vault
      // const notes = await obsidianService.listNotes(id, { search, tag, folder, modifiedSince }, page, pageSize)

      // Mock data
      const mockNotes = [
        {
          id: crypto.randomUUID(),
          vaultId: id,
          title: 'Meeting Notes - 2025-02-15',
          path: 'Work/Meetings/2025-02-15.md',
          folder: 'Work/Meetings',
          tags: ['meeting', 'project-alpha'],
          wordCount: 850,
          createdAt: new Date(Date.now() - 86400000).toISOString(),
          modifiedAt: new Date(Date.now() - 3600000).toISOString(),
          excerpt: 'Discussed project timeline and deliverables...',
        },
        {
          id: crypto.randomUUID(),
          vaultId: id,
          title: 'Research - AI Agents',
          path: 'Research/AI-Agents.md',
          folder: 'Research',
          tags: ['ai', 'research', 'agents'],
          wordCount: 2340,
          createdAt: new Date(Date.now() - 172800000).toISOString(),
          modifiedAt: new Date(Date.now() - 7200000).toISOString(),
          excerpt: 'Exploring multi-agent systems and coordination...',
        },
      ];

      const totalItems = mockNotes.length;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: mockNotes,
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
 * POST /api/v1/obsidian/vaults/:id/notes
 * Create new note in vault
 */
router.post(
  '/vaults/:id/notes',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: z.object({
      title: z.string().min(1).max(200),
      content: z.string(),
      folder: z.string().optional(),
      tags: z.array(z.string()).optional(),
      frontmatter: z.record(z.any()).optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { title, content, folder, tags, frontmatter } = req.body;

      // TODO: Create note in vault
      // const note = await obsidianService.createNote(id, { title, content, folder, tags, frontmatter })

      // Mock response
      const sanitizedTitle = title.replace(/[^a-zA-Z0-9-_\s]/g, '');
      const path = folder ? `${folder}/${sanitizedTitle}.md` : `${sanitizedTitle}.md`;

      const note = {
        id: crypto.randomUUID(),
        vaultId: id,
        title,
        path,
        folder: folder || '',
        tags: tags || [],
        frontmatter,
        wordCount: content.split(/\s+/).length,
        createdAt: new Date().toISOString(),
        modifiedAt: new Date().toISOString(),
      };

      res.status(201).json({
        success: true,
        data: note,
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
 * POST /api/v1/obsidian/vaults/:id/sync
 * Manually trigger vault sync
 */
router.post(
  '/vaults/:id/sync',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Trigger sync
      // const result = await obsidianService.syncVault(id)

      // Mock response
      const result = {
        vaultId: id,
        notesScanned: 1247,
        notesAdded: 3,
        notesUpdated: 12,
        notesDeleted: 1,
        duration: 2340, // ms
        syncedAt: new Date().toISOString(),
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
 * GET /api/v1/obsidian/vaults/:vaultId/notes/:noteId
 * Get note content
 */
router.get(
  '/vaults/:vaultId/notes/:noteId',
  validateRequest({
    params: z.object({
      vaultId: z.string().uuid(),
      noteId: z.string().uuid(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { vaultId, noteId } = req.params;

      // TODO: Fetch note content
      // const note = await obsidianService.getNote(vaultId, noteId)

      // Mock data
      const note = {
        id: noteId,
        vaultId,
        title: 'Meeting Notes - 2025-02-15',
        path: 'Work/Meetings/2025-02-15.md',
        folder: 'Work/Meetings',
        tags: ['meeting', 'project-alpha'],
        frontmatter: {
          date: '2025-02-15',
          attendees: ['Alice', 'Bob', 'Charlie'],
        },
        content: `---
date: 2025-02-15
attendees:
  - Alice
  - Bob
  - Charlie
tags:
  - meeting
  - project-alpha
---

# Meeting Notes - 2025-02-15

## Agenda
1. Project timeline review
2. Resource allocation
3. Next steps

## Discussion
...
`,
        wordCount: 850,
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        modifiedAt: new Date(Date.now() - 3600000).toISOString(),
      };

      res.json({
        success: true,
        data: note,
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
