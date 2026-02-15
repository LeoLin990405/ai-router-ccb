/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Model service - handles AI providers and models
 */

import { ProviderRepository, ModelRepository } from '../repositories';
import type { Provider, NewProvider, Model, NewModel } from '../schema';

export class ModelService {
  private providerRepo: ProviderRepository;
  private modelRepo: ModelRepository;

  constructor() {
    this.providerRepo = new ProviderRepository();
    this.modelRepo = new ModelRepository();
  }

  // === Provider Operations ===

  /**
   * Get all providers
   */
  async getProviders(): Promise<Provider[]> {
    return this.providerRepo.findAll();
  }

  /**
   * Get enabled providers only
   */
  async getEnabledProviders(): Promise<Provider[]> {
    return this.providerRepo.findEnabled();
  }

  /**
   * Get provider by ID
   */
  async getProvider(providerId: string): Promise<Provider | null> {
    return this.providerRepo.findById(providerId);
  }

  /**
   * Get provider by name
   */
  async getProviderByName(name: string): Promise<Provider | null> {
    return this.providerRepo.findByName(name);
  }

  /**
   * Create a new provider
   */
  async createProvider(data: {
    name: string;
    type: 'google' | 'anthropic' | 'openai' | 'custom';
    apiKey?: string;
    baseUrl?: string;
    config?: any;
    enabled?: boolean;
  }): Promise<Provider> {
    // Check if provider already exists
    const existing = await this.providerRepo.findByName(data.name);
    if (existing) {
      throw new Error('Provider with this name already exists');
    }

    const newProvider: NewProvider = {
      name: data.name,
      type: data.type,
      apiKey: data.apiKey,
      baseUrl: data.baseUrl,
      config: data.config,
      enabled: data.enabled ?? true,
    };

    return this.providerRepo.createProvider(newProvider);
  }

  /**
   * Update provider configuration
   */
  async updateProvider(
    providerId: string,
    data: {
      name?: string;
      apiKey?: string;
      baseUrl?: string;
      config?: any;
      enabled?: boolean;
    }
  ): Promise<Provider | null> {
    const provider = await this.providerRepo.findById(providerId);
    if (!provider) {
      throw new Error('Provider not found');
    }

    return this.providerRepo.updateProvider(providerId, data);
  }

  /**
   * Enable/disable provider
   */
  async toggleProvider(providerId: string, enabled: boolean): Promise<Provider | null> {
    return this.providerRepo.setEnabled(providerId, enabled);
  }

  /**
   * Delete provider
   */
  async deleteProvider(providerId: string): Promise<boolean> {
    return this.providerRepo.deleteById(providerId);
  }

  // === Model Operations ===

  /**
   * Get all models
   */
  async getModels(): Promise<Model[]> {
    return this.modelRepo.findAll();
  }

  /**
   * Get all models with provider info
   */
  async getModelsWithProvider() {
    return this.modelRepo.findAllWithProvider();
  }

  /**
   * Get enabled models only
   */
  async getEnabledModels(): Promise<Model[]> {
    return this.modelRepo.findEnabled();
  }

  /**
   * Get model by ID
   */
  async getModel(modelId: string): Promise<Model | null> {
    return this.modelRepo.findById(modelId);
  }

  /**
   * Get model by ID with provider info
   */
  async getModelWithProvider(modelId: string) {
    return this.modelRepo.findByIdWithProvider(modelId);
  }

  /**
   * Get model by name
   */
  async getModelByName(name: string): Promise<Model | null> {
    return this.modelRepo.findByName(name);
  }

  /**
   * Get models for a provider
   */
  async getProviderModels(providerId: string): Promise<Model[]> {
    return this.modelRepo.findByProvider(providerId);
  }

  /**
   * Create a new model
   */
  async createModel(data: {
    name: string;
    displayName: string;
    providerId: string;
    modelId: string;
    capabilities?: any;
    contextWindow?: number;
    maxOutputTokens?: number;
    enabled?: boolean;
  }): Promise<Model> {
    // Verify provider exists
    const provider = await this.providerRepo.findById(data.providerId);
    if (!provider) {
      throw new Error('Provider not found');
    }

    // Check if model already exists
    const existing = await this.modelRepo.findByName(data.name);
    if (existing) {
      throw new Error('Model with this name already exists');
    }

    const newModel: NewModel = {
      name: data.name,
      displayName: data.displayName,
      providerId: data.providerId,
      modelId: data.modelId,
      capabilities: data.capabilities,
      contextWindow: data.contextWindow,
      maxOutputTokens: data.maxOutputTokens,
      enabled: data.enabled ?? true,
    };

    return this.modelRepo.createModel(newModel);
  }

  /**
   * Update model configuration
   */
  async updateModel(
    modelId: string,
    data: {
      displayName?: string;
      modelId?: string;
      capabilities?: any;
      contextWindow?: number;
      maxOutputTokens?: number;
      enabled?: boolean;
    }
  ): Promise<Model | null> {
    const model = await this.modelRepo.findById(modelId);
    if (!model) {
      throw new Error('Model not found');
    }

    return this.modelRepo.updateModel(modelId, data);
  }

  /**
   * Enable/disable model
   */
  async toggleModel(modelId: string, enabled: boolean): Promise<Model | null> {
    return this.modelRepo.setEnabled(modelId, enabled);
  }

  /**
   * Delete model
   */
  async deleteModel(modelId: string): Promise<boolean> {
    return this.modelRepo.deleteById(modelId);
  }
}
