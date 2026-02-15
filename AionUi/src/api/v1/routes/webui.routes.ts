/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * WebUI management routes
 */

import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { validateRequest } from '../middleware/validate';
import { authenticateJWT, requireRole } from '../middleware/auth';

const router = Router();

// Validation schemas
const changePasswordSchema = z.object({
  newPassword: z.string().min(8, 'Password must be at least 8 characters'),
});

/**
 * GET /api/v1/webui/status
 * Get WebUI server status
 */
router.get('/status', async (req: Request, res: Response, next: NextFunction) => {
  try {
    // TODO: Get actual WebUI status from configuration
    const status = {
      enabled: process.env.WEBUI_ENABLED === 'true',
      port: parseInt(process.env.WEBUI_PORT || '8080', 10),
      host: process.env.WEBUI_HOST || 'localhost',
      requiresAuth: process.env.WEBUI_REQUIRE_AUTH !== 'false',
      hasPassword: Boolean(process.env.WEBUI_PASSWORD),
      qrEnabled: process.env.WEBUI_QR_ENABLED === 'true',
    };

    res.json({
      success: true,
      data: status,
      meta: {
        timestamp: new Date().toISOString(),
        requestId: crypto.randomUUID(),
      },
    });
  } catch (error) {
    next(error);
  }
});

/**
 * POST /api/v1/webui/change-password
 * Change WebUI password (admin only)
 */
router.post(
  '/change-password',
  authenticateJWT,
  requireRole('admin'),
  validateRequest({ body: changePasswordSchema }),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { newPassword } = req.body;

      // TODO: Implement actual password change logic
      // For now, just validate and return success
      // In production, this should:
      // 1. Hash the password
      // 2. Update environment variable or config file
      // 3. Restart WebUI server if needed

      // Mock implementation
      console.log('WebUI password change requested by:', req.user?.username);
      console.log('New password length:', newPassword.length);

      res.json({
        success: true,
        data: {
          message: 'WebUI password changed successfully',
          requiresRestart: false, // Set to true if WebUI needs restart
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
 * POST /api/v1/webui/reset-password
 * Reset WebUI password to default (admin only)
 */
router.post(
  '/reset-password',
  authenticateJWT,
  requireRole('admin'),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      // TODO: Implement actual password reset logic
      console.log('WebUI password reset requested by:', req.user?.username);

      res.json({
        success: true,
        data: {
          message: 'WebUI password reset to default',
          defaultPassword: 'admin', // In production, generate a random password
          requiresRestart: false,
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
 * POST /api/v1/webui/qr-token
 * Generate QR code token for mobile access
 */
router.post(
  '/qr-token',
  authenticateJWT,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      // Generate a temporary token for QR code
      const token = crypto.randomUUID();
      const expiresIn = 300; // 5 minutes
      const expiresAt = new Date(Date.now() + expiresIn * 1000);

      // TODO: Store token in database or cache (Redis)
      // For now, just return the token
      // In production:
      // 1. Store token with expiration
      // 2. Associate with current user
      // 3. Generate QR code data URL

      const qrData = JSON.stringify({
        token,
        userId: req.user?.userId,
        expiresAt: expiresAt.toISOString(),
        serverUrl: process.env.WEBUI_URL || `http://localhost:${process.env.WEBUI_PORT || 8080}`,
      });

      res.json({
        success: true,
        data: {
          token,
          qrData,
          expiresIn,
          expiresAt: expiresAt.toISOString(),
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
 * GET /api/v1/webui/config
 * Get WebUI configuration (admin only)
 */
router.get(
  '/config',
  authenticateJWT,
  requireRole('admin'),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const config = {
        enabled: process.env.WEBUI_ENABLED === 'true',
        port: parseInt(process.env.WEBUI_PORT || '8080', 10),
        host: process.env.WEBUI_HOST || 'localhost',
        requireAuth: process.env.WEBUI_REQUIRE_AUTH !== 'false',
        qrEnabled: process.env.WEBUI_QR_ENABLED === 'true',
        maxConnections: parseInt(process.env.WEBUI_MAX_CONNECTIONS || '10', 10),
        allowedOrigins: process.env.WEBUI_ALLOWED_ORIGINS?.split(',') || ['*'],
      };

      res.json({
        success: true,
        data: config,
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
 * PUT /api/v1/webui/config
 * Update WebUI configuration (admin only)
 */
router.put(
  '/config',
  authenticateJWT,
  requireRole('admin'),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { enabled, port, host, requireAuth, qrEnabled, maxConnections, allowedOrigins } =
        req.body;

      // TODO: Implement actual config update logic
      // In production:
      // 1. Validate configuration
      // 2. Update config file or environment
      // 3. Restart WebUI server if needed

      console.log('WebUI config update requested by:', req.user?.username);
      console.log('New config:', req.body);

      res.json({
        success: true,
        data: {
          message: 'WebUI configuration updated',
          requiresRestart: true,
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

export default router;
