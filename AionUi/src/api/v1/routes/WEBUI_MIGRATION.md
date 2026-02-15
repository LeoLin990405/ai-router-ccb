# WebUI Migration Guide

Guide for migrating WebUI components from Electron IPC to REST API.

## API Endpoints

### WebUI Status

**Before (Electron)**:
```typescript
const status = await window.electronAPI.webuiGetStatus();
```

**After (HTTP)**:
```typescript
import { api } from '@/services/api';

const status = await api.http.get('/webui/status');
```

---

### Change Password

**Before (Electron)**:
```typescript
await window.electronAPI.webuiChangePassword(newPassword);
```

**After (HTTP)**:
```typescript
import { api } from '@/services/api';

await api.http.post('/webui/change-password', {
  newPassword,
});
```

---

### Generate QR Token

**Before (Electron)**:
```typescript
const qrData = await window.electronAPI.webuiGenerateQRToken();
```

**After (HTTP)**:
```typescript
import { api } from '@/services/api';

const result = await api.http.post('/webui/qr-token');
// result.token, result.qrData, result.expiresIn
```

---

### Reset Password

**Before (Electron)**:
```typescript
await window.electronAPI.webuiResetPassword();
```

**After (HTTP)**:
```typescript
import { api } from '@/services/api';

await api.http.post('/webui/reset-password');
```

---

## File Upload

### Upload Single File

**Before (Electron)**:
```typescript
const filePath = window.electronAPI.getPathForFile(file);
```

**After (HTTP)**:
```typescript
import { api } from '@/services/api';

const formData = new FormData();
formData.append('file', file);

const result = await fetch('/api/v1/upload/single', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${tokenStorage.getAccessToken()}`,
  },
  body: formData,
});

const { data } = await result.json();
// data.path, data.url, data.filename
```

### Upload Multiple Files

```typescript
const formData = new FormData();
files.forEach(file => {
  formData.append('files', file);
});

const result = await fetch('/api/v1/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${tokenStorage.getAccessToken()}`,
  },
  body: formData,
});

const { data } = await result.json();
// data.files[], data.count
```

---

## Component Migration Example

### WebuiModalContent.tsx

**Before**:
```typescript
const [status, setStatus] = useState(null);

useEffect(() => {
  async function fetchStatus() {
    if (window.electronAPI?.webuiGetStatus) {
      const result = await window.electronAPI.webuiGetStatus();
      setStatus(result);
    }
  }
  fetchStatus();
}, []);

const handleChangePassword = async (newPassword: string) => {
  if (window.electronAPI?.webuiChangePassword) {
    await window.electronAPI.webuiChangePassword(newPassword);
  }
};
```

**After**:
```typescript
import { api } from '@/services/api';

const [status, setStatus] = useState(null);

useEffect(() => {
  async function fetchStatus() {
    try {
      const result = await api.http.get('/webui/status');
      setStatus(result);
    } catch (error) {
      console.error('Failed to fetch WebUI status:', error);
    }
  }
  fetchStatus();
}, []);

const handleChangePassword = async (newPassword: string) => {
  try {
    await api.http.post('/webui/change-password', { newPassword });
    // Show success message
  } catch (error) {
    console.error('Failed to change password:', error);
    // Show error message
  }
};
```

---

## File Drag & Drop Migration

**Before**:
```typescript
const handleDrop = (event: DragEvent) => {
  const files = Array.from(event.dataTransfer.files);

  files.forEach(file => {
    if (window.electronAPI?.getPathForFile) {
      const filePath = window.electronAPI.getPathForFile(file);
      console.log('File path:', filePath);
    }
  });
};
```

**After**:
```typescript
import { api } from '@/services/api';

const handleDrop = async (event: DragEvent) => {
  const files = Array.from(event.dataTransfer.files);

  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });

  try {
    const result = await fetch('/api/v1/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${tokenStorage.getAccessToken()}`,
      },
      body: formData,
    });

    const { data } = await result.json();
    data.files.forEach(file => {
      console.log('Uploaded:', file.url);
    });
  } catch (error) {
    console.error('Upload failed:', error);
  }
};
```

---

## Environment Detection

Use the unified client to automatically select the right transport:

```typescript
import { api } from '@/services/api';

// Automatically uses Electron IPC or HTTP based on environment
const status = await api.call('webui/status');
```

Or check explicitly:

```typescript
import { isElectron } from '@/services/api';

if (isElectron()) {
  // Use Electron-specific features
  if (api.electron) {
    const path = api.electron.getPathForFile(file);
  }
} else {
  // Use web-specific features
  const result = await fetch('/api/v1/upload/single', {
    method: 'POST',
    body: formData,
  });
}
```

---

## Error Handling

**Electron IPC** (no structured errors):
```typescript
try {
  await window.electronAPI.webuiChangePassword(pwd);
} catch (error) {
  // Generic error
}
```

**HTTP API** (structured errors):
```typescript
try {
  await api.http.post('/webui/change-password', { newPassword: pwd });
} catch (error) {
  // error.message contains the error description
  // Can check for specific error codes
  if (error.message.includes('UNAUTHORIZED')) {
    // Handle auth error
  } else if (error.message.includes('VALIDATION_ERROR')) {
    // Handle validation error
  }
}
```

---

## Testing

1. **Test in Electron mode**:
   - Run `npm start`
   - Verify all WebUI features work
   - Check console for errors

2. **Test in browser mode**:
   - Run `npm run dev` (Vite dev server)
   - Verify all WebUI features work via HTTP
   - Check network tab for API calls

3. **Test file uploads**:
   - Drag & drop files
   - Verify files are uploaded to server
   - Check uploaded files list

---

## Checklist

- [ ] WebuiModalContent.tsx migrated
- [ ] File drag & drop updated
- [ ] Error handling implemented
- [ ] Loading states added
- [ ] Success/error messages shown
- [ ] Tested in Electron mode
- [ ] Tested in browser mode
- [ ] File uploads working
- [ ] API authentication working
