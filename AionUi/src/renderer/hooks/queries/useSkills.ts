/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Skills React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/renderer/config/queryClient';
import { api } from '@/renderer/services/api';

/**
 * Skill interface
 */
export interface Skill {
  id: string;
  name: string;
  description: string;
  path: string;
  triggers: string[];
  enabled: boolean;
  version?: string;
  author?: string;
  metadata?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

/**
 * List skills filters
 */
export interface ListSkillsFilters {
  page?: number;
  limit?: number;
  enabled?: boolean;
  search?: string;
}

/**
 * List skills response
 */
export interface ListSkillsResponse {
  skills: Skill[];
  pagination: {
    total: number;
    page: number;
    limit: number;
    totalPages: number;
  };
}

/**
 * Create skill request
 */
export interface CreateSkillRequest {
  name: string;
  description: string;
  path: string;
  triggers?: string[];
  enabled?: boolean;
}

/**
 * Update skill request
 */
export interface UpdateSkillRequest {
  name?: string;
  description?: string;
  triggers?: string[];
  enabled?: boolean;
}

/**
 * Fetch skills list
 */
async function fetchSkills(filters: ListSkillsFilters = {}): Promise<ListSkillsResponse> {
  const response = await api.call<{ success: boolean; data: ListSkillsResponse }>(
    'skills.list',
    filters
  );

  if (!response.success || !response.data) {
    throw new Error('Failed to fetch skills');
  }

  return response.data;
}

/**
 * Fetch skill by ID
 */
async function fetchSkill(id: string): Promise<Skill> {
  const response = await api.call<{ success: boolean; data: Skill }>('skills.get', { id });

  if (!response.success || !response.data) {
    throw new Error('Skill not found');
  }

  return response.data;
}

/**
 * Create skill
 */
async function createSkill(data: CreateSkillRequest): Promise<Skill> {
  const response = await api.call<{ success: boolean; data: Skill }>('skills.create', data);

  if (!response.success || !response.data) {
    throw new Error('Failed to create skill');
  }

  return response.data;
}

/**
 * Update skill
 */
async function updateSkill(id: string, data: UpdateSkillRequest): Promise<Skill> {
  const response = await api.call<{ success: boolean; data: Skill }>('skills.update', {
    id,
    ...data,
  });

  if (!response.success || !response.data) {
    throw new Error('Failed to update skill');
  }

  return response.data;
}

/**
 * Delete skill
 */
async function deleteSkill(id: string): Promise<void> {
  const response = await api.call<{ success: boolean }>('skills.delete', { id });

  if (!response.success) {
    throw new Error('Failed to delete skill');
  }
}

/**
 * Toggle skill enabled state
 */
async function toggleSkill(id: string, enabled: boolean): Promise<Skill> {
  return updateSkill(id, { enabled });
}

/**
 * Hook: List skills
 */
export function useSkills(filters: ListSkillsFilters = {}) {
  return useQuery({
    queryKey: queryKeys.skills.list(filters),
    queryFn: () => fetchSkills(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes (skills don't change often)
  });
}

/**
 * Hook: Get skill by ID
 */
export function useSkill(id: string) {
  return useQuery({
    queryKey: queryKeys.skills.detail(id),
    queryFn: () => fetchSkill(id),
    enabled: !!id,
  });
}

/**
 * Hook: Create skill
 */
export function useCreateSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createSkill,
    onSuccess: (newSkill) => {
      // Invalidate skills list
      queryClient.invalidateQueries({ queryKey: queryKeys.skills.lists() });
      // Set the new skill in cache
      queryClient.setQueryData(queryKeys.skills.detail(newSkill.id), newSkill);
    },
  });
}

/**
 * Hook: Update skill
 */
export function useUpdateSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateSkillRequest }) => updateSkill(id, data),
    onSuccess: (updatedSkill) => {
      // Update skill in cache
      queryClient.setQueryData(queryKeys.skills.detail(updatedSkill.id), updatedSkill);
      // Invalidate skills list
      queryClient.invalidateQueries({ queryKey: queryKeys.skills.lists() });
    },
  });
}

/**
 * Hook: Delete skill
 */
export function useDeleteSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteSkill,
    onSuccess: (_, deletedId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: queryKeys.skills.detail(deletedId) });
      // Invalidate skills list
      queryClient.invalidateQueries({ queryKey: queryKeys.skills.lists() });
    },
  });
}

/**
 * Hook: Toggle skill (with optimistic update)
 */
export function useToggleSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => toggleSkill(id, enabled),
    // Optimistic update
    onMutate: async ({ id, enabled }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.skills.detail(id) });

      // Snapshot previous value
      const previousSkill = queryClient.getQueryData<Skill>(queryKeys.skills.detail(id));

      // Optimistically update
      if (previousSkill) {
        queryClient.setQueryData<Skill>(queryKeys.skills.detail(id), {
          ...previousSkill,
          enabled,
        });
      }

      // Return context with previous value
      return { previousSkill };
    },
    // On error, roll back
    onError: (err, { id }, context) => {
      if (context?.previousSkill) {
        queryClient.setQueryData(queryKeys.skills.detail(id), context.previousSkill);
      }
    },
    // Always refetch after error or success
    onSettled: (_, __, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skills.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.skills.lists() });
    },
  });
}
