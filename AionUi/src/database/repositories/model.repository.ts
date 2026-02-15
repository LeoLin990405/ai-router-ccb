/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { eq, and } from 'drizzle-orm';
import { BaseRepository } from './base.repository';
import { providers, models, type Provider, type NewProvider, type Model, type NewModel } from '../schema';
import { db } from '../db';

export class ProviderRepository extends BaseRepository<typeof providers> {
  constructor() {
    super(providers);
  }

  /**
   * Find provider by name
   */
  async findByName(name: string): Promise<Provider | null> {
    return this.findOne(eq(providers.name, name));
  }

  /**
   * Find all enabled providers
   */
  async findEnabled(): Promise<Provider[]> {
    return this.findAll(eq(providers.enabled, true));
  }

  /**
   * Create a new provider
   */
  async createProvider(data: NewProvider): Promise<Provider> {
    return this.create(data);
  }

  /**
   * Update provider configuration
   */
  async updateProvider(
    providerId: string,
    data: Partial<Pick<Provider, 'name' | 'apiKey' | 'baseUrl' | 'config' | 'enabled'>>
  ): Promise<Provider | null> {
    return this.updateById(providerId, data);
  }

  /**
   * Enable/disable provider
   */
  async setEnabled(providerId: string, enabled: boolean): Promise<Provider | null> {
    return this.updateById(providerId, { enabled });
  }
}

export class ModelRepository extends BaseRepository<typeof models> {
  constructor() {
    super(models);
  }

  /**
   * Find model by name
   */
  async findByName(name: string): Promise<Model | null> {
    return this.findOne(eq(models.name, name));
  }

  /**
   * Find all models for a provider
   */
  async findByProvider(providerId: string): Promise<Model[]> {
    return this.findAll(eq(models.providerId, providerId));
  }

  /**
   * Find all enabled models
   */
  async findEnabled(): Promise<Model[]> {
    return this.findAll(eq(models.enabled, true));
  }

  /**
   * Find model with provider info
   */
  async findByIdWithProvider(modelId: string) {
    const results = await db
      .select()
      .from(models)
      .leftJoin(providers, eq(models.providerId, providers.id))
      .where(eq(models.id, modelId))
      .limit(1);

    if (!results[0]) return null;

    return {
      ...results[0].models,
      provider: results[0].providers,
    };
  }

  /**
   * Find all models with provider info
   */
  async findAllWithProvider() {
    const results = await db
      .select()
      .from(models)
      .leftJoin(providers, eq(models.providerId, providers.id))
      .where(eq(models.enabled, true));

    return results.map((r) => ({
      ...r.models,
      provider: r.providers,
    }));
  }

  /**
   * Create a new model
   */
  async createModel(data: NewModel): Promise<Model> {
    return this.create(data);
  }

  /**
   * Update model configuration
   */
  async updateModel(
    modelId: string,
    data: Partial<
      Pick<
        Model,
        'displayName' | 'modelId' | 'capabilities' | 'contextWindow' | 'maxOutputTokens' | 'enabled'
      >
    >
  ): Promise<Model | null> {
    return this.updateById(modelId, data);
  }

  /**
   * Enable/disable model
   */
  async setEnabled(modelId: string, enabled: boolean): Promise<Model | null> {
    return this.updateById(modelId, { enabled });
  }
}
