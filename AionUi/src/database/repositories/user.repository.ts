/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { eq, or } from 'drizzle-orm';
import { BaseRepository } from './base.repository';
import { users, refreshTokens, type User, type NewUser, type RefreshToken } from '../schema';
import { db } from '../db';

export class UserRepository extends BaseRepository<typeof users> {
  constructor() {
    super(users);
  }

  /**
   * Find user by username
   */
  async findByUsername(username: string): Promise<User | null> {
    return this.findOne(eq(users.username, username));
  }

  /**
   * Find user by email
   */
  async findByEmail(email: string): Promise<User | null> {
    return this.findOne(eq(users.email, email));
  }

  /**
   * Find user by username or email
   */
  async findByUsernameOrEmail(usernameOrEmail: string): Promise<User | null> {
    return this.findOne(or(eq(users.username, usernameOrEmail), eq(users.email, usernameOrEmail))!);
  }

  /**
   * Create a new user
   */
  async createUser(data: NewUser): Promise<User> {
    return this.create(data);
  }

  /**
   * Update user profile
   */
  async updateProfile(
    userId: string,
    data: Partial<Pick<User, 'displayName' | 'avatarUrl' | 'bio' | 'preferences'>>
  ): Promise<User | null> {
    return this.updateById(userId, data);
  }

  /**
   * Update user password
   */
  async updatePassword(userId: string, passwordHash: string): Promise<User | null> {
    return this.updateById(userId, { passwordHash });
  }

  /**
   * Enable/disable two-factor authentication
   */
  async updateTwoFactor(userId: string, enabled: boolean, secret?: string): Promise<User | null> {
    return this.updateById(userId, {
      twoFactorEnabled: enabled,
      twoFactorSecret: secret || null,
    });
  }

  /**
   * Verify user email
   */
  async verifyEmail(userId: string): Promise<User | null> {
    return this.updateById(userId, {
      emailVerified: true,
      emailVerifiedAt: new Date(),
    });
  }

  /**
   * Update last login timestamp
   */
  async updateLastLogin(userId: string): Promise<User | null> {
    return this.updateById(userId, { lastLoginAt: new Date() });
  }

  // === Refresh Token Operations ===

  /**
   * Create a refresh token
   */
  async createRefreshToken(data: {
    userId: string;
    token: string;
    expiresAt: Date;
  }): Promise<RefreshToken> {
    const results = await db.insert(refreshTokens).values(data).returning();
    return results[0];
  }

  /**
   * Find refresh token
   */
  async findRefreshToken(token: string): Promise<RefreshToken | null> {
    const results = await db
      .select()
      .from(refreshTokens)
      .where(eq(refreshTokens.token, token))
      .limit(1);
    return results[0] || null;
  }

  /**
   * Revoke refresh token
   */
  async revokeRefreshToken(token: string): Promise<boolean> {
    const results = await db
      .update(refreshTokens)
      .set({ revokedAt: new Date() })
      .where(eq(refreshTokens.token, token))
      .returning();
    return results.length > 0;
  }

  /**
   * Delete expired refresh tokens
   */
  async deleteExpiredTokens(): Promise<number> {
    const results = await db
      .delete(refreshTokens)
      .where(eq(refreshTokens.expiresAt, new Date()))
      .returning();
    return results.length;
  }

  /**
   * Delete all user refresh tokens
   */
  async deleteUserTokens(userId: string): Promise<number> {
    const results = await db
      .delete(refreshTokens)
      .where(eq(refreshTokens.userId, userId))
      .returning();
    return results.length;
  }
}
