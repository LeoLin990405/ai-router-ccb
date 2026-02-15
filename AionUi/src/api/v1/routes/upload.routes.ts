/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * File upload routes
 */

import { Router, Request, Response, NextFunction } from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs/promises';
import crypto from 'crypto';
import { authenticateJWT } from '../middleware/auth';

const router = Router();

// Configure multer for file uploads
const uploadsDir = process.env.UPLOADS_DIR || path.join(process.cwd(), 'uploads');

// Ensure uploads directory exists
fs.mkdir(uploadsDir, { recursive: true }).catch((err) => {
  console.error('Failed to create uploads directory:', err);
});

// Configure storage
const storage = multer.diskStorage({
  destination: async (req, file, cb) => {
    // Create user-specific directory
    const userId = (req as any).user?.userId || 'anonymous';
    const userDir = path.join(uploadsDir, userId);

    try {
      await fs.mkdir(userDir, { recursive: true });
      cb(null, userDir);
    } catch (error: any) {
      cb(error, userDir);
    }
  },
  filename: (req, file, cb) => {
    // Generate unique filename
    const uniqueSuffix = `${Date.now()}-${crypto.randomBytes(6).toString('hex')}`;
    const ext = path.extname(file.originalname);
    const basename = path.basename(file.originalname, ext);
    const safeBasename = basename.replace(/[^a-z0-9_-]/gi, '_');
    cb(null, `${safeBasename}-${uniqueSuffix}${ext}`);
  },
});

// File filter
const fileFilter = (req: Request, file: Express.Multer.File, cb: multer.FileFilterCallback) => {
  // Allowed file types
  const allowedTypes = [
    // Images
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'image/svg+xml',
    // Documents
    'application/pdf',
    'text/plain',
    'text/markdown',
    'application/json',
    // Code
    'text/javascript',
    'text/typescript',
    'text/css',
    'text/html',
    // Archives
    'application/zip',
    'application/x-tar',
    'application/gzip',
  ];

  if (allowedTypes.includes(file.mimetype) || file.mimetype.startsWith('text/')) {
    cb(null, true);
  } else {
    cb(new Error(`File type ${file.mimetype} not allowed`));
  }
};

// Create multer instance
const upload = multer({
  storage,
  fileFilter,
  limits: {
    fileSize: parseInt(process.env.MAX_FILE_SIZE || '10485760', 10), // 10MB default
    files: parseInt(process.env.MAX_FILES_PER_UPLOAD || '10', 10),
  },
});

/**
 * POST /api/v1/upload
 * Upload multiple files
 */
router.post(
  '/',
  authenticateJWT,
  upload.array('files', 10),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const files = req.files as Express.Multer.File[];

      if (!files || files.length === 0) {
        return res.status(400).json({
          success: false,
          error: {
            code: 'NO_FILES',
            message: 'No files uploaded',
          },
        });
      }

      // Process uploaded files
      const uploadedFiles = files.map((file) => ({
        filename: file.filename,
        originalName: file.originalname,
        path: file.path,
        size: file.size,
        mimetype: file.mimetype,
        url: `/api/v1/upload/${req.user!.userId}/${file.filename}`,
      }));

      res.json({
        success: true,
        data: {
          files: uploadedFiles,
          count: uploadedFiles.length,
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
 * POST /api/v1/upload/single
 * Upload a single file
 */
router.post(
  '/single',
  authenticateJWT,
  upload.single('file'),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const file = req.file;

      if (!file) {
        return res.status(400).json({
          success: false,
          error: {
            code: 'NO_FILE',
            message: 'No file uploaded',
          },
        });
      }

      res.json({
        success: true,
        data: {
          filename: file.filename,
          originalName: file.originalname,
          path: file.path,
          size: file.size,
          mimetype: file.mimetype,
          url: `/api/v1/upload/${req.user!.userId}/${file.filename}`,
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
 * GET /api/v1/upload/:userId/:filename
 * Download/view an uploaded file
 */
router.get(
  '/:userId/:filename',
  authenticateJWT,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { userId, filename } = req.params;

      // Security check: users can only access their own files (unless admin)
      if (userId !== req.user!.userId && req.user!.role !== 'admin') {
        return res.status(403).json({
          success: false,
          error: {
            code: 'FORBIDDEN',
            message: 'You can only access your own files',
          },
        });
      }

      const filePath = path.join(uploadsDir, userId, filename);

      // Check if file exists
      try {
        await fs.access(filePath);
      } catch {
        return res.status(404).json({
          success: false,
          error: {
            code: 'FILE_NOT_FOUND',
            message: 'File not found',
          },
        });
      }

      // Send file
      res.sendFile(filePath);
    } catch (error) {
      next(error);
    }
  }
);

/**
 * DELETE /api/v1/upload/:userId/:filename
 * Delete an uploaded file
 */
router.delete(
  '/:userId/:filename',
  authenticateJWT,
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { userId, filename } = req.params;

      // Security check
      if (userId !== req.user!.userId && req.user!.role !== 'admin') {
        return res.status(403).json({
          success: false,
          error: {
            code: 'FORBIDDEN',
            message: 'You can only delete your own files',
          },
        });
      }

      const filePath = path.join(uploadsDir, userId, filename);

      // Check if file exists
      try {
        await fs.access(filePath);
      } catch {
        return res.status(404).json({
          success: false,
          error: {
            code: 'FILE_NOT_FOUND',
            message: 'File not found',
          },
        });
      }

      // Delete file
      await fs.unlink(filePath);

      res.json({
        success: true,
        data: {
          message: 'File deleted successfully',
          filename,
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
 * GET /api/v1/upload/list
 * List user's uploaded files
 */
router.get('/list', authenticateJWT, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const userId = req.user!.userId;
    const userDir = path.join(uploadsDir, userId);

    // Check if directory exists
    try {
      await fs.access(userDir);
    } catch {
      // Directory doesn't exist, return empty list
      return res.json({
        success: true,
        data: {
          files: [],
          count: 0,
        },
        meta: {
          timestamp: new Date().toISOString(),
          requestId: crypto.randomUUID(),
        },
      });
    }

    // Read directory
    const files = await fs.readdir(userDir);

    // Get file stats
    const fileList = await Promise.all(
      files.map(async (filename) => {
        const filePath = path.join(userDir, filename);
        const stats = await fs.stat(filePath);

        return {
          filename,
          size: stats.size,
          createdAt: stats.birthtime,
          modifiedAt: stats.mtime,
          url: `/api/v1/upload/${userId}/${filename}`,
        };
      })
    );

    // Sort by creation date (newest first)
    fileList.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

    res.json({
      success: true,
      data: {
        files: fileList,
        count: fileList.length,
      },
      meta: {
        timestamp: new Date().toISOString(),
        requestId: crypto.randomUUID(),
      },
    });
  } catch (error) {
    next(error);
  }
});

export default router;
