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

// All MCP routes require authentication
router.use(authenticateJWT);

/**
 * GET /api/v1/mcp/servers
 * List all MCP servers
 */
router.get(
  '/servers',
  validateRequest({
    query: paginationQuerySchema.extend({
      enabled: z.coerce.boolean().optional(),
      status: z.enum(['connected', 'disconnected', 'error']).optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { page, pageSize, enabled, status } = req.query as any;

      // TODO: Fetch from MCP service
      // const servers = await mcpService.listServers({ enabled, status }, page, pageSize)

      // Mock data
      const mockServers = [
        {
          id: crypto.randomUUID(),
          name: 'filesystem',
          displayName: 'File System',
          description: 'Access and manipulate local files',
          command: 'npx',
          args: ['-y', '@modelcontextprotocol/server-filesystem', '/workspace'],
          enabled: true,
          status: 'connected' as const,
          capabilities: {
            tools: true,
            resources: true,
            prompts: false,
          },
          toolCount: 8,
          resourceCount: 0,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          id: crypto.randomUUID(),
          name: 'github',
          displayName: 'GitHub',
          description: 'Interact with GitHub repositories',
          command: 'npx',
          args: ['-y', '@modelcontextprotocol/server-github'],
          env: { GITHUB_TOKEN: '***masked***' },
          enabled: true,
          status: 'connected' as const,
          capabilities: {
            tools: true,
            resources: true,
            prompts: true,
          },
          toolCount: 25,
          resourceCount: 5,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ];

      const totalItems = mockServers.length;
      const totalPages = Math.ceil(totalItems / pageSize);

      res.json({
        success: true,
        data: mockServers,
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
 * POST /api/v1/mcp/servers
 * Add new MCP server
 */
router.post(
  '/servers',
  validateRequest({
    body: z.object({
      name: z.string().min(1).max(100),
      displayName: z.string().min(1).max(200),
      description: z.string().optional(),
      command: z.string(),
      args: z.array(z.string()).optional(),
      env: z.record(z.string()).optional(),
      enabled: z.boolean().default(true),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const data = req.body;

      // TODO: Add server to MCP service
      // const server = await mcpService.addServer(data)

      // Mock response
      const server = {
        id: crypto.randomUUID(),
        ...data,
        status: 'disconnected' as const,
        capabilities: {
          tools: false,
          resources: false,
          prompts: false,
        },
        toolCount: 0,
        resourceCount: 0,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.status(201).json({
        success: true,
        data: server,
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
 * GET /api/v1/mcp/servers/:id
 * Get MCP server details
 */
router.get(
  '/servers/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Fetch from MCP service
      // const server = await mcpService.getServer(id)

      // Mock data
      const server = {
        id,
        name: 'github',
        displayName: 'GitHub',
        description: 'Interact with GitHub repositories',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-github'],
        env: { GITHUB_TOKEN: '***masked***' },
        enabled: true,
        status: 'connected' as const,
        capabilities: {
          tools: true,
          resources: true,
          prompts: true,
        },
        toolCount: 25,
        resourceCount: 5,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.json({
        success: true,
        data: server,
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
 * PATCH /api/v1/mcp/servers/:id
 * Update MCP server
 */
router.patch(
  '/servers/:id',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: z.object({
      displayName: z.string().optional(),
      description: z.string().optional(),
      args: z.array(z.string()).optional(),
      env: z.record(z.string()).optional(),
      enabled: z.boolean().optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const updates = req.body;

      // TODO: Update in MCP service
      // const server = await mcpService.updateServer(id, updates)

      // Mock response
      const server = {
        id,
        name: 'github',
        displayName: updates.displayName || 'GitHub',
        description: updates.description || 'Interact with GitHub repositories',
        command: 'npx',
        args: updates.args || ['-y', '@modelcontextprotocol/server-github'],
        env: updates.env || { GITHUB_TOKEN: '***masked***' },
        enabled: updates.enabled ?? true,
        status: 'connected' as const,
        capabilities: {
          tools: true,
          resources: true,
          prompts: true,
        },
        toolCount: 25,
        resourceCount: 5,
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        updatedAt: new Date().toISOString(),
      };

      res.json({
        success: true,
        data: server,
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
 * DELETE /api/v1/mcp/servers/:id
 * Remove MCP server
 */
router.delete(
  '/servers/:id',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Remove from MCP service
      // await mcpService.removeServer(id)

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
 * GET /api/v1/mcp/servers/:id/tools
 * List tools provided by server
 */
router.get(
  '/servers/:id/tools',
  validateRequest({ params: z.object({ id: z.string().uuid() }) }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;

      // TODO: Fetch tools from MCP service
      // const tools = await mcpService.listTools(id)

      // Mock data
      const tools = [
        {
          name: 'create_issue',
          description: 'Create a new GitHub issue',
          inputSchema: {
            type: 'object',
            properties: {
              title: { type: 'string' },
              body: { type: 'string' },
              labels: { type: 'array', items: { type: 'string' } },
            },
            required: ['title'],
          },
        },
        {
          name: 'list_issues',
          description: 'List issues from a repository',
          inputSchema: {
            type: 'object',
            properties: {
              state: { type: 'string', enum: ['open', 'closed', 'all'] },
              labels: { type: 'array', items: { type: 'string' } },
            },
          },
        },
      ];

      res.json({
        success: true,
        data: tools,
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
 * POST /api/v1/mcp/servers/:id/call
 * Call MCP server tool
 */
router.post(
  '/servers/:id/call',
  validateRequest({
    params: z.object({ id: z.string().uuid() }),
    body: z.object({
      tool: z.string(),
      arguments: z.record(z.any()).optional(),
    }),
  }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { id } = req.params;
      const { tool, arguments: args } = req.body;

      // TODO: Call tool via MCP service
      // const result = await mcpService.callTool(id, tool, args)

      // Mock response
      const result = {
        tool,
        success: true,
        result: {
          message: `Tool ${tool} executed successfully with arguments: ${JSON.stringify(args)}`,
          data: {
            id: crypto.randomUUID(),
            status: 'completed',
          },
        },
        executedAt: new Date().toISOString(),
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
