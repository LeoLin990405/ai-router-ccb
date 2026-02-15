# R001 - Electron Dependency Analysis

**Date**: 2026-02-15
**Analyst**: Claude Sonnet 4.5
**Goal**: Document all Electron dependencies for migration to standalone React SPA

---

## Executive Summary

The frontend code is already well-abstracted with minimal Electron dependencies. Most interactions go through `window.electronAPI`, which is a good abstraction layer. The migration should be straightforward with proper API client replacement.

### Key Findings

- **Total Electron API usage**: ~20 call sites
- **Main communication method**: `window.electronAPI.emit()` (bridge pattern)
- **Direct IPC calls**: 4 specific methods for WebUI features
- **File handling**: Uses `webUtils.getPathForFile()` for drag-and-drop

---

## 1. Electron API Exposed via Preload

Located in: `src/preload.ts`

```typescript
window.electronAPI = {
  // General bridge communication
  emit: (name: string, data: any) => Promise<any>,
  on: (callback: (data: any) => void) => UnsubscribeFn,

  // File utilities
  getPathForFile: (file: File) => string,

  // WebUI specific (direct IPC)
  webuiResetPassword: () => Promise<any>,
  webuiGetStatus: () => Promise<any>,
  webuiChangePassword: (newPassword: string) => Promise<any>,
  webuiGenerateQRToken: () => Promise<any>,
}
```

---

## 2. Usage Locations

### 2.1 Platform Detection

**Files**:
- `src/renderer/utils/platform.ts`
- `src/renderer/context/AuthContext.tsx`
- `src/renderer/components/SettingsModal/contents/AboutModalContent.tsx`
- `src/renderer/pages/conversation/preview/components/renderers/HTMLRenderer.tsx`

**Pattern**:
```typescript
const isElectron = typeof window !== 'undefined' && Boolean(window.electronAPI);
```

**Migration**:
- Replace with environment variable or build-time constant
- Set to `false` in pure web build

### 2.2 WebUI Settings

**File**: `src/renderer/components/SettingsModal/contents/WebuiModalContent.tsx`

**APIs Used**:
- `window.electronAPI.webuiGetStatus()`
- `window.electronAPI.webuiChangePassword(newPassword)`
- `window.electronAPI.webuiGenerateQRToken()`

**Migration**:
- `webuiGetStatus()` → `GET /api/v1/webui/status`
- `webuiChangePassword()` → `POST /api/v1/webui/change-password`
- `webuiGenerateQRToken()` → `POST /api/v1/webui/qr-token`

### 2.3 File Drag & Drop

**Files**:
- `src/renderer/pages/conversation/workspace/hooks/useWorkspaceDragImport.ts`
- `src/renderer/services/FileService.ts`

**Pattern**:
```typescript
if (window.electronAPI?.getPathForFile) {
  filePath = window.electronAPI.getPathForFile(file);
} else {
  const electronFile = file as File & { path?: string };
  filePath = electronFile.path;
}
```

**Migration**:
- In browser, `file.path` doesn't exist
- Use `file.name` for display
- Upload file to server, get server path
- Or use File API directly without path

### 2.4 Bridge Communication (emit/on)

**Pattern**: Code uses a bridge library that wraps `window.electronAPI.emit()`

**Migration Strategy**:
- Replace `window.electronAPI.emit()` with HTTP client calls
- Replace `window.electronAPI.on()` with WebSocket event listeners
- Create adapter that maps old bridge calls to new API calls

---

## 3. Migration Strategy

### Phase 1: Create API Client Abstraction (R001-1/5)

Create a unified API client that works both in Electron and browser:

```typescript
// src/renderer/services/api-client.ts
interface APIClient {
  call<T>(method: string, data?: any): Promise<T>;
  subscribe(event: string, callback: (data: any) => void): UnsubscribeFn;
}

// Electron implementation
class ElectronAPIClient implements APIClient {
  call<T>(method: string, data?: any): Promise<T> {
    return window.electronAPI.emit(method, data);
  }
  subscribe(event: string, callback: (data: any) => void) {
    return window.electronAPI.on(callback);
  }
}

// HTTP implementation
class HTTPAPIClient implements APIClient {
  async call<T>(method: string, data?: any): Promise<T> {
    const response = await fetch(`/api/v1/${method}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAccessToken()}`,
      },
      body: JSON.stringify(data),
    });
    return response.json();
  }
  subscribe(event: string, callback: (data: any) => void) {
    // WebSocket implementation
    socket.on(event, callback);
    return () => socket.off(event, callback);
  }
}

// Factory
export const apiClient: APIClient =
  typeof window.electronAPI !== 'undefined'
    ? new ElectronAPIClient()
    : new HTTPAPIClient();
```

### Phase 2: Replace Direct IPC Calls (R001-2/5)

Create REST API endpoints for WebUI features:

```typescript
// Before
await window.electronAPI.webuiGetStatus();

// After
await apiClient.call('webui/status');
// Or
await fetch('/api/v1/webui/status').then(r => r.json());
```

### Phase 3: Handle File Operations (R001-3/5)

Replace file path handling:

```typescript
// Before
const filePath = window.electronAPI.getPathForFile(file);

// After
const formData = new FormData();
formData.append('file', file);
const response = await fetch('/api/v1/files/upload', {
  method: 'POST',
  body: formData,
});
const { path } = await response.json();
```

### Phase 4: Remove Electron Checks (R001-4/5)

Replace all `isElectron` checks with environment variables:

```typescript
// vite.config.ts
export default defineConfig({
  define: {
    'import.meta.env.IS_ELECTRON': false,
    'import.meta.env.IS_WEB': true,
  },
});

// Usage
const isElectron = import.meta.env.IS_ELECTRON;
```

### Phase 5: Test & Cleanup (R001-5/5)

- Remove `src/preload.ts`
- Remove Electron imports
- Test all features in browser
- Verify no runtime Electron dependencies

---

## 4. API Endpoint Mapping

| Electron API Call | HTTP Endpoint | Method | Notes |
|-------------------|---------------|--------|-------|
| `webuiGetStatus()` | `/api/v1/webui/status` | GET | WebUI status |
| `webuiChangePassword()` | `/api/v1/webui/change-password` | POST | Password update |
| `webuiGenerateQRToken()` | `/api/v1/webui/qr-token` | POST | QR code for mobile |
| `getPathForFile()` | `/api/v1/files/upload` | POST | File upload |
| Bridge `emit()` | `/api/v1/bridge/:method` | POST | Generic bridge call |
| Bridge `on()` | WebSocket events | WS | Real-time updates |

---

## 5. Risk Assessment

### Low Risk ✅
- Platform detection (simple environment variable)
- WebUI API calls (straightforward REST mapping)
- Most features already use HTTP API

### Medium Risk ⚠️
- File drag & drop (need to implement file upload)
- Bridge communication (need to map all methods)

### High Risk 🔴
- None identified (code is already well-abstracted)

---

## 6. Dependencies to Install

```bash
# HTTP client
npm install axios

# WebSocket
npm install socket.io-client

# Optional: React Query for server state
npm install @tanstack/react-query
```

---

## 7. Build System Changes

### Current: Electron Forge + Webpack

```json
{
  "scripts": {
    "start": "electron-forge start",
    "package": "electron-forge package",
    "make": "electron-forge make"
  }
}
```

### Target: Vite + React

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

---

## 8. Next Steps

### Session R001-1/5 ✅ (This session)
- ✅ Analyzed Electron dependencies
- ✅ Created migration strategy
- ✅ Documented API mapping

### Session R001-2/5
- Create API client abstraction layer
- Implement HTTP client with auth
- Set up proxy configuration for dev

### Session R001-3/5
- Replace WebUI API calls with REST
- Implement file upload endpoint
- Handle drag & drop in browser

### Session R001-4/5
- Set up Vite for React
- Migrate from hash to browser routing
- Remove Electron checks

### Session R001-5/5
- Test all features in browser
- Remove Electron dependencies
- Update documentation

---

## 9. Acceptance Criteria Checklist

- [ ] Frontend runs independently in browser without Electron
- [ ] All UI components render correctly in browser
- [ ] No Electron dependencies in frontend code
- [ ] Development server starts with 'npm run dev:frontend'
- [ ] All existing features work via HTTP API calls

---

## 10. Resources

- [Electron to Web Migration Guide](https://vitejs.dev/guide/)
- [React Router v6 Browser Router](https://reactrouter.com/en/main)
- [Vite Configuration](https://vitejs.dev/config/)
- [Socket.IO Client](https://socket.io/docs/v4/client-api/)

---

**Status**: Analysis Complete ✅
**Ready for**: R001-2/5 Implementation
