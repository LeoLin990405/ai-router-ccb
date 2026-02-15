# React Query & Zustand Usage Examples

## Overview

This document provides examples of how to use React Query hooks and Zustand stores in HiveMind components.

## React Query Hooks

### Authentication

```typescript
import { useAuthState, useLogin, useLogout } from '@/renderer/hooks/queries';

function LoginForm() {
  const { user, isLoading, isAuthenticated } = useAuthState();
  const loginMutation = useLogin();

  const handleLogin = async (credentials: { username: string; password: string }) => {
    try {
      await loginMutation.mutateAsync(credentials);
      // User is now logged in, cache is updated
    } catch (error) {
      // Error is handled by global error handler
      console.error('Login failed:', error);
    }
  };

  if (isLoading) return <div>Loading...</div>;
  if (isAuthenticated) return <div>Welcome, {user?.username}!</div>;

  return <form onSubmit={handleLogin}>...</form>;
}
```

### Conversations List

```typescript
import { useConversations, useCreateConversation } from '@/renderer/hooks/queries';

function ConversationsList() {
  const { data, isLoading, error } = useConversations({ status: 'active', limit: 20 });
  const createConversation = useCreateConversation();

  const handleCreate = async () => {
    try {
      const newConv = await createConversation.mutateAsync({
        title: 'New Conversation',
      });
      // List will auto-update thanks to cache invalidation
      console.log('Created:', newConv.id);
    } catch (error) {
      console.error('Failed to create:', error);
    }
  };

  if (isLoading) return <div>Loading conversations...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <button onClick={handleCreate}>New Conversation</button>
      {data?.conversations.map((conv) => (
        <div key={conv.id}>{conv.title}</div>
      ))}
    </div>
  );
}
```

### Messages with Optimistic Updates

```typescript
import { useConversationMessages, useCreateMessage } from '@/renderer/hooks/queries';

function ChatMessages({ conversationId }: { conversationId: string }) {
  const { data: messages, isLoading } = useConversationMessages(conversationId);
  const createMessage = useCreateMessage();

  const handleSend = async (content: string) => {
    // Optimistic update: message appears immediately
    await createMessage.mutateAsync({
      conversationId,
      content,
      role: 'user',
    });
    // If successful, temp message is replaced with real one
    // If failed, temp message is removed and error is shown
  };

  if (isLoading) return <div>Loading messages...</div>;

  return (
    <div>
      {messages?.map((msg) => (
        <div key={msg.id} className={msg.id.startsWith('temp-') ? 'opacity-50' : ''}>
          {msg.content}
        </div>
      ))}
    </div>
  );
}
```

### Skills with Toggle

```typescript
import { useSkills, useToggleSkill } from '@/renderer/hooks/queries';

function SkillsList() {
  const { data, isLoading } = useSkills({ enabled: true });
  const toggleSkill = useToggleSkill();

  const handleToggle = async (id: string, enabled: boolean) => {
    // Optimistic update: checkbox changes immediately
    await toggleSkill.mutateAsync({ id, enabled });
    // On error, checkbox reverts to previous state
  };

  if (isLoading) return <div>Loading skills...</div>;

  return (
    <div>
      {data?.skills.map((skill) => (
        <div key={skill.id}>
          <label>
            <input
              type="checkbox"
              checked={skill.enabled}
              onChange={(e) => handleToggle(skill.id, e.target.checked)}
            />
            {skill.name}
          </label>
        </div>
      ))}
    </div>
  );
}
```

## Zustand Stores

### UI Store

```typescript
import { useUIStore, uiSelectors } from '@/renderer/stores';

function Sidebar() {
  // Using selector for optimized re-renders
  const collapsed = useUIStore(uiSelectors.sidebarCollapsed);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);

  return (
    <div className={collapsed ? 'w-16' : 'w-64'}>
      <button onClick={toggleSidebar}>Toggle</button>
    </div>
  );
}

function NotificationCenter() {
  const notifications = useUIStore(uiSelectors.notifications);
  const removeNotification = useUIStore((state) => state.removeNotification);

  return (
    <div>
      {notifications.map((notif) => (
        <div key={notif.id}>
          <span>{notif.message}</span>
          <button onClick={() => removeNotification(notif.id)}>Dismiss</button>
        </div>
      ))}
    </div>
  );
}

function GlobalLoading() {
  const { globalLoading, loadingMessage } = useUIStore((state) => ({
    globalLoading: state.globalLoading,
    loadingMessage: state.loadingMessage,
  }));

  if (!globalLoading) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="spinner" />
      {loadingMessage && <p>{loadingMessage}</p>}
    </div>
  );
}
```

### Conversation Store

```typescript
import { useConversationStore, conversationSelectors } from '@/renderer/stores';

function MessageInput({ conversationId }: { conversationId: string }) {
  const draft = useConversationStore((state) => state.getDraft(conversationId));
  const saveDraft = useConversationStore((state) => state.saveDraft);
  const clearDraft = useConversationStore((state) => state.clearDraft);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    saveDraft(conversationId, e.target.value);
  };

  const handleSend = () => {
    // Send message...
    clearDraft(conversationId);
  };

  return (
    <div>
      <textarea value={draft} onChange={handleChange} />
      <button onClick={handleSend}>Send</button>
    </div>
  );
}

function TypingIndicator({ conversationId }: { conversationId: string }) {
  const typingUsers = useConversationStore(conversationSelectors.typingUsers(conversationId));

  if (typingUsers.length === 0) return null;

  return <div>{typingUsers.join(', ')} is typing...</div>;
}
```

## Combining React Query + Zustand

```typescript
import { useConversationMessages, useCreateMessage } from '@/renderer/hooks/queries';
import { useConversationStore } from '@/renderer/stores';

function ChatInterface({ conversationId }: { conversationId: string }) {
  // Server state (React Query)
  const { data: messages, isLoading } = useConversationMessages(conversationId);
  const createMessage = useCreateMessage();

  // Client state (Zustand)
  const draft = useConversationStore((state) => state.getDraft(conversationId));
  const saveDraft = useConversationStore((state) => state.saveDraft);
  const clearDraft = useConversationStore((state) => state.clearDraft);
  const scrollToBottom = useConversationStore(conversationSelectors.scrollToBottom);
  const setScrollToBottom = useConversationStore((state) => state.setScrollToBottom);

  const handleSend = async () => {
    if (!draft.trim()) return;

    try {
      await createMessage.mutateAsync({
        conversationId,
        content: draft,
        role: 'user',
      });
      clearDraft(conversationId);
      setScrollToBottom(true);
    } catch (error) {
      console.error('Failed to send:', error);
    }
  };

  return (
    <div>
      {/* Messages (server state) */}
      <div className="messages">
        {isLoading ? <div>Loading...</div> : null}
        {messages?.map((msg) => (
          <div key={msg.id}>{msg.content}</div>
        ))}
      </div>

      {/* Input (client state) */}
      <div className="input">
        <textarea
          value={draft}
          onChange={(e) => saveDraft(conversationId, e.target.value)}
        />
        <button onClick={handleSend} disabled={createMessage.isPending}>
          {createMessage.isPending ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
```

## Best Practices

### 1. Use Selectors

```typescript
// ✅ Good: Only re-renders when sidebarCollapsed changes
const collapsed = useUIStore(uiSelectors.sidebarCollapsed);

// ❌ Bad: Re-renders on any state change
const { sidebarCollapsed } = useUIStore();
```

### 2. Combine Multiple Selectors Carefully

```typescript
// ✅ Good: Use object selector for multiple values
const { collapsed, width } = useUIStore((state) => ({
  collapsed: state.sidebarCollapsed,
  width: state.sidebarWidth,
}));

// ❌ Bad: Multiple subscriptions
const collapsed = useUIStore((state) => state.sidebarCollapsed);
const width = useUIStore((state) => state.sidebarWidth);
```

### 3. Handle Loading and Error States

```typescript
function MyComponent() {
  const { data, isLoading, error } = useConversations();

  if (isLoading) return <Spinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return <EmptyState />;

  return <ConversationsList conversations={data.conversations} />;
}
```

### 4. Use Optimistic Updates for Better UX

```typescript
// User sees immediate feedback
// If operation fails, UI reverts automatically
const toggleSkill = useToggleSkill();

<Switch
  checked={skill.enabled}
  onChange={(checked) => toggleSkill.mutate({ id: skill.id, enabled: checked })}
/>
```

### 5. Separate Server State from Client State

```typescript
// Server state: Data from API (use React Query)
const { data: conversations } = useConversations();

// Client state: UI preferences (use Zustand)
const sidebarCollapsed = useUIStore((state) => state.sidebarCollapsed);
```

## Migration Guide

### From Context to React Query

**Before (Context):**
```typescript
const { conversations, loading, error, fetchConversations } = useConversationContext();

useEffect(() => {
  fetchConversations();
}, []);
```

**After (React Query):**
```typescript
const { data: conversations, isLoading, error } = useConversations();
// No need for useEffect, React Query handles fetching
```

### From useState to Zustand

**Before (useState):**
```typescript
const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
// State is lost on unmount, need manual persistence
```

**After (Zustand):**
```typescript
const collapsed = useUIStore((state) => state.sidebarCollapsed);
const toggle = useUIStore((state) => state.toggleSidebar);
// State persists, shared across components
```
