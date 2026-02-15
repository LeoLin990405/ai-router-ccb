/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Service layer exports
 */

export { UserService } from './user.service';
export { ConversationService } from './conversation.service';
export { ModelService } from './model.service';

// Singleton service instances
export const userService = new UserService();
export const conversationService = new ConversationService();
export const modelService = new ModelService();
