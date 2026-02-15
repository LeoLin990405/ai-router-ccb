/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Users React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/renderer/config/queryClient';
import { api } from '@/renderer/services/api';
import type { User } from './useAuth';

/**
 * List users filters
 */
export interface ListUsersFilters {
  page?: number;
  limit?: number;
  role?: 'admin' | 'user';
  search?: string;
}

/**
 * List users response
 */
export interface ListUsersResponse {
  users: User[];
  pagination: {
    total: number;
    page: number;
    limit: number;
    totalPages: number;
  };
}

/**
 * Update user request
 */
export interface UpdateUserRequest {
  email?: string;
  role?: 'admin' | 'user';
  displayName?: string;
  avatar?: string;
  bio?: string;
}

/**
 * Fetch users list
 */
async function fetchUsers(filters: ListUsersFilters = {}): Promise<ListUsersResponse> {
  const response = await api.call<{ success: boolean; data: ListUsersResponse }>(
    'admin.users.list',
    filters
  );

  if (!response.success || !response.data) {
    throw new Error('Failed to fetch users');
  }

  return response.data;
}

/**
 * Fetch user by ID
 */
async function fetchUser(id: string): Promise<User> {
  const response = await api.call<{ success: boolean; data: User }>('admin.users.get', { id });

  if (!response.success || !response.data) {
    throw new Error('User not found');
  }

  return response.data;
}

/**
 * Update user
 */
async function updateUser(id: string, data: UpdateUserRequest): Promise<User> {
  const response = await api.call<{ success: boolean; data: User }>('admin.users.update', {
    id,
    ...data,
  });

  if (!response.success || !response.data) {
    throw new Error('Failed to update user');
  }

  return response.data;
}

/**
 * Delete user
 */
async function deleteUser(id: string): Promise<void> {
  const response = await api.call<{ success: boolean }>('admin.users.delete', { id });

  if (!response.success) {
    throw new Error('Failed to delete user');
  }
}

/**
 * Reset user password (admin)
 */
async function resetUserPassword(id: string): Promise<{ resetToken: string }> {
  const response = await api.call<{ success: boolean; data: { resetToken: string } }>(
    'admin.users.resetPassword',
    { id }
  );

  if (!response.success || !response.data) {
    throw new Error('Failed to reset password');
  }

  return response.data;
}

/**
 * Hook: List users
 */
export function useUsers(filters: ListUsersFilters = {}) {
  return useQuery({
    queryKey: queryKeys.users.list(filters),
    queryFn: () => fetchUsers(filters),
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
}

/**
 * Hook: Get user by ID
 */
export function useUser(id: string) {
  return useQuery({
    queryKey: queryKeys.users.detail(id),
    queryFn: () => fetchUser(id),
    enabled: !!id,
  });
}

/**
 * Hook: Update user
 */
export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateUserRequest }) => updateUser(id, data),
    onSuccess: (updatedUser) => {
      // Update user in cache
      queryClient.setQueryData(queryKeys.users.detail(updatedUser.id), updatedUser);
      // Invalidate users list
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    },
  });
}

/**
 * Hook: Delete user
 */
export function useDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteUser,
    onSuccess: (_, deletedId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: queryKeys.users.detail(deletedId) });
      // Invalidate users list
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
    },
  });
}

/**
 * Hook: Reset user password
 */
export function useResetUserPassword() {
  return useMutation({
    mutationFn: resetUserPassword,
  });
}
