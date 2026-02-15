# Database Integration Guide

This guide explains how to integrate the database service layer with the REST API routes.

## Architecture Overview

```
Client Request
    ↓
API Routes (src/api/v1/routes/*.routes.ts)
    ↓
Service Layer (src/database/services/*.service.ts)
    ↓
Repository Layer (src/database/repositories/*.repository.ts)
    ↓
Drizzle ORM (src/database/db.ts)
    ↓
PostgreSQL Database
```

## Service Layer

The service layer provides business logic and abstracts database operations:

- **UserService**: User authentication and management
- **ConversationService**: Conversation and message management
- **ModelService**: AI providers and models management
- **SkillService**: Skills management
- **CronService**: Scheduled tasks management

## Integration Examples

### 1. Authentication Routes

**File**: `src/api/v1/routes/auth.routes.ts`

```typescript
import { userService } from '@/database/services';
import { generateTokenPair, generateRandomToken, getRefreshTokenExpiration } from '@/database/utils/jwt.util';

// Register endpoint
router.post('/register', validateRequest({ body: registerRequestSchema }), async (req, res, next) => {
  try {
    const { username, email, password, displayName } = req.body;

    // Create user using service
    const user = await userService.register({
      username,
      email,
      password,
      displayName,
    });

    // Generate JWT tokens
    const { accessToken, refreshToken, expiresIn } = generateTokenPair({
      userId: user.id,
      username: user.username,
      role: user.role,
    });

    // Store refresh token
    const refreshTokenHash = generateRandomToken();
    await userService.createRefreshToken(
      user.id,
      refreshTokenHash,
      getRefreshTokenExpiration()
    );

    res.status(201).json({
      success: true,
      data: {
        accessToken,
        refreshToken: refreshTokenHash,
        expiresIn,
        user: {
          id: user.id,
          username: user.username,
          email: user.email,
          role: user.role,
          displayName: user.displayName,
          createdAt: user.createdAt,
        },
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

// Login endpoint
router.post('/login', validateRequest({ body: loginRequestSchema }), async (req, res, next) => {
  try {
    const { username, password } = req.body;

    // Authenticate user
    const user = await userService.authenticate(username, password);

    if (!user) {
      return res.status(401).json({
        success: false,
        error: {
          code: 'INVALID_CREDENTIALS',
          message: 'Invalid username or password',
        },
      });
    }

    // Generate tokens
    const { accessToken, refreshToken, expiresIn } = generateTokenPair({
      userId: user.id,
      username: user.username,
      role: user.role,
    });

    // Store refresh token
    const refreshTokenHash = generateRandomToken();
    await userService.createRefreshToken(
      user.id,
      refreshTokenHash,
      getRefreshTokenExpiration()
    );

    res.json({
      success: true,
      data: {
        accessToken,
        refreshToken: refreshTokenHash,
        expiresIn,
        user: {
          id: user.id,
          username: user.username,
          email: user.email,
          role: user.role,
          displayName: user.displayName,
        },
      },
    });
  } catch (error) {
    next(error);
  }
});
```

### 2. Conversation Routes

**File**: `src/api/v1/routes/conversation.routes.ts`

```typescript
import { conversationService } from '@/database/services';

// List conversations
router.get('/', validateRequest({ query: listConversationsQuerySchema }), async (req, res, next) => {
  try {
    const userId = req.user.userId; // From JWT middleware
    const { page = 1, pageSize = 20 } = req.query;

    const conversations = await conversationService.getUserConversations(userId, {
      limit: pageSize,
      offset: (page - 1) * pageSize,
    });

    res.json({
      success: true,
      data: conversations,
      pagination: {
        page,
        pageSize,
        totalItems: conversations.length,
      },
    });
  } catch (error) {
    next(error);
  }
});

// Create conversation
router.post('/', validateRequest({ body: createConversationRequestSchema }), async (req, res, next) => {
  try {
    const userId = req.user.userId;
    const { name, platform, model, systemPrompt } = req.body;

    const conversation = await conversationService.createConversation({
      userId,
      name,
      platform,
      model,
      systemPrompt,
    });

    res.status(201).json({
      success: true,
      data: conversation,
    });
  } catch (error) {
    next(error);
  }
});

// Get conversation messages
router.get('/:id/messages', async (req, res, next) => {
  try {
    const userId = req.user.userId;
    const conversationId = req.params.id;
    const { page = 1, pageSize = 100 } = req.query;

    const messages = await conversationService.getMessages(conversationId, userId, {
      limit: pageSize,
      offset: (page - 1) * pageSize,
    });

    res.json({
      success: true,
      data: messages,
    });
  } catch (error) {
    next(error);
  }
});

// Send message
router.post('/:id/messages', validateRequest({ body: sendMessageRequestSchema }), async (req, res, next) => {
  try {
    const userId = req.user.userId;
    const conversationId = req.params.id;
    const { role, content, attachments } = req.body;

    const message = await conversationService.addMessage(conversationId, userId, {
      role,
      content,
      attachments,
    });

    res.status(201).json({
      success: true,
      data: message,
    });
  } catch (error) {
    next(error);
  }
});
```

### 3. Model Routes

**File**: `src/api/v1/routes/model.routes.ts`

```typescript
import { modelService } from '@/database/services';

// List all models with providers
router.get('/', async (req, res, next) => {
  try {
    const models = await modelService.getModelsWithProvider();

    res.json({
      success: true,
      data: models,
    });
  } catch (error) {
    next(error);
  }
});

// Get model by ID
router.get('/:id', async (req, res, next) => {
  try {
    const model = await modelService.getModelWithProvider(req.params.id);

    if (!model) {
      return res.status(404).json({
        success: false,
        error: {
          code: 'MODEL_NOT_FOUND',
          message: 'Model not found',
        },
      });
    }

    res.json({
      success: true,
      data: model,
    });
  } catch (error) {
    next(error);
  }
});

// Create new model
router.post('/', async (req, res, next) => {
  try {
    const model = await modelService.createModel(req.body);

    res.status(201).json({
      success: true,
      data: model,
    });
  } catch (error) {
    next(error);
  }
});
```

## Error Handling

Wrap service calls in try-catch blocks and use the Express error handling middleware:

```typescript
try {
  const result = await service.someMethod();
  res.json({ success: true, data: result });
} catch (error) {
  next(error); // Pass to error handler
}
```

Common error patterns:

```typescript
// Not found
if (!entity) {
  return res.status(404).json({
    success: false,
    error: {
      code: 'ENTITY_NOT_FOUND',
      message: 'Entity not found',
    },
  });
}

// Unauthorized
if (!hasAccess) {
  return res.status(403).json({
    success: false,
    error: {
      code: 'ACCESS_DENIED',
      message: 'You do not have permission to access this resource',
    },
  });
}

// Validation error
if (!isValid) {
  return res.status(400).json({
    success: false,
    error: {
      code: 'VALIDATION_ERROR',
      message: 'Invalid input data',
      details: validationErrors,
    },
  });
}
```

## Transaction Support

For operations that require multiple database writes:

```typescript
import { db } from '@/database/db';

async function complexOperation() {
  return await db.transaction(async (tx) => {
    // All operations use 'tx' instead of 'db'
    const user = await tx.insert(users).values({...}).returning();
    const conversation = await tx.insert(conversations).values({...}).returning();

    return { user, conversation };
  });
}
```

## Testing with Database

Use the seed script for development data:

```bash
npm run db:seed
```

Default test users:
- Admin: `admin@hivemind.local` / `password123`
- Demo: `demo@hivemind.local` / `password123`

## Migration Workflow

1. Modify schemas in `src/database/schema/*.ts`
2. Generate migration: `npm run db:generate`
3. Review migration file in `database/migrations/`
4. Apply migration: `npm run db:migrate`

For development, you can use `npm run db:push` to push schema changes directly without generating migration files.

## Best Practices

1. **Always validate input** using Zod schemas before passing to services
2. **Check ownership** before modifying resources (conversations, messages, etc.)
3. **Use services, not repositories** directly in routes
4. **Handle errors gracefully** with appropriate HTTP status codes
5. **Use transactions** for operations that modify multiple tables
6. **Sanitize output** - don't expose sensitive fields like passwordHash
7. **Add indexes** for frequently queried fields
8. **Use connection pooling** - already configured in db.ts

## Next Steps

1. Replace TODO comments in route files with actual service calls
2. Implement JWT middleware for protected routes
3. Add input sanitization and rate limiting
4. Implement proper error logging
5. Add API documentation with OpenAPI/Swagger
