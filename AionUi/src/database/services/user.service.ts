/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * User service - handles user authentication and management
 */

import bcrypt from 'bcrypt';
import { UserRepository } from '../repositories';
import type { User, NewUser } from '../schema';

export class UserService {
  private userRepo: UserRepository;

  constructor() {
    this.userRepo = new UserRepository();
  }

  /**
   * Register a new user
   */
  async register(data: {
    username: string;
    email: string;
    password: string;
    displayName?: string;
  }): Promise<User> {
    // Check if user already exists
    const existingUser = await this.userRepo.findByUsernameOrEmail(data.username);
    if (existingUser) {
      throw new Error('Username or email already exists');
    }

    // Hash password
    const passwordHash = await bcrypt.hash(data.password, 10);

    // Create user
    const newUser: NewUser = {
      username: data.username,
      email: data.email,
      passwordHash,
      displayName: data.displayName || data.username,
      role: 'user',
    };

    return this.userRepo.createUser(newUser);
  }

  /**
   * Authenticate user with username/email and password
   */
  async authenticate(usernameOrEmail: string, password: string): Promise<User | null> {
    const user = await this.userRepo.findByUsernameOrEmail(usernameOrEmail);
    if (!user) {
      return null;
    }

    const isValid = await bcrypt.compare(password, user.passwordHash);
    if (!isValid) {
      return null;
    }

    // Update last login
    await this.userRepo.updateLastLogin(user.id);

    return user;
  }

  /**
   * Get user by ID
   */
  async getUserById(userId: string): Promise<User | null> {
    return this.userRepo.findById(userId);
  }

  /**
   * Get user by username
   */
  async getUserByUsername(username: string): Promise<User | null> {
    return this.userRepo.findByUsername(username);
  }

  /**
   * Update user profile
   */
  async updateProfile(
    userId: string,
    data: {
      displayName?: string;
      avatarUrl?: string;
      bio?: string;
      preferences?: any;
    }
  ): Promise<User | null> {
    return this.userRepo.updateProfile(userId, data);
  }

  /**
   * Change user password
   */
  async changePassword(userId: string, oldPassword: string, newPassword: string): Promise<boolean> {
    const user = await this.userRepo.findById(userId);
    if (!user) {
      throw new Error('User not found');
    }

    // Verify old password
    const isValid = await bcrypt.compare(oldPassword, user.passwordHash);
    if (!isValid) {
      throw new Error('Invalid old password');
    }

    // Hash new password
    const passwordHash = await bcrypt.hash(newPassword, 10);

    // Update password
    await this.userRepo.updatePassword(userId, passwordHash);
    return true;
  }

  /**
   * Enable two-factor authentication
   */
  async enableTwoFactor(userId: string, secret: string): Promise<User | null> {
    return this.userRepo.updateTwoFactor(userId, true, secret);
  }

  /**
   * Disable two-factor authentication
   */
  async disableTwoFactor(userId: string): Promise<User | null> {
    return this.userRepo.updateTwoFactor(userId, false);
  }

  /**
   * Verify user email
   */
  async verifyEmail(userId: string): Promise<User | null> {
    return this.userRepo.verifyEmail(userId);
  }

  /**
   * Create refresh token
   */
  async createRefreshToken(userId: string, token: string, expiresAt: Date) {
    return this.userRepo.createRefreshToken({ userId, token, expiresAt });
  }

  /**
   * Validate refresh token
   */
  async validateRefreshToken(token: string) {
    const refreshToken = await this.userRepo.findRefreshToken(token);
    if (!refreshToken) {
      return null;
    }

    // Check if expired
    if (refreshToken.expiresAt < new Date()) {
      return null;
    }

    // Check if revoked
    if (refreshToken.revokedAt) {
      return null;
    }

    return refreshToken;
  }

  /**
   * Revoke refresh token
   */
  async revokeRefreshToken(token: string): Promise<boolean> {
    return this.userRepo.revokeRefreshToken(token);
  }

  /**
   * Revoke all user tokens
   */
  async revokeAllUserTokens(userId: string): Promise<number> {
    return this.userRepo.deleteUserTokens(userId);
  }

  /**
   * Clean up expired tokens
   */
  async cleanupExpiredTokens(): Promise<number> {
    return this.userRepo.deleteExpiredTokens();
  }
}
