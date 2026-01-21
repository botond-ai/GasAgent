/**
 * Application-wide constants and configuration
 * 
 * Environment variables must be defined in .env file.
 * This file enforces strict env var validation (no fallbacks).
 */

// ===== API Configuration =====

/**
 * Backend API base URL (must be set in .env as VITE_API_URL)
 * Example: http://localhost:8000/api
 */
export const API_BASE_URL = import.meta.env.VITE_API_URL;

if (!API_BASE_URL) {
  throw new Error(
    'VITE_API_URL environment variable is required. ' +
    'Please create a .env file with VITE_API_URL=http://localhost:8000/api'
  );
}

/**
 * WebSocket base URL (derived from API_BASE_URL)
 * Handles both absolute URLs (http://...) and relative URLs (/api)
 */
export const getWebSocketUrl = (sessionId: string): string => {
  // If API_BASE_URL is relative (e.g., /api), use current host
  if (API_BASE_URL.startsWith('/')) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/ws/workflow/${sessionId}`;
  }
  
  // If API_BASE_URL is absolute (e.g., http://localhost:8000/api)
  const baseUrl = API_BASE_URL
    .replace('/api', '')
    .replace('http://', '')
    .replace('https://', '');
  return `ws://${baseUrl}/ws/workflow/${sessionId}`;
};

// ===== UI Timeouts =====

/**
 * Success message auto-hide duration (milliseconds)
 */
export const SUCCESS_MESSAGE_DURATION = 3000;

/**
 * WebSocket ping interval to keep connection alive (milliseconds)
 */
export const WS_PING_INTERVAL = 30000;

/**
 * Debug stats auto-refresh interval (milliseconds)
 */
export const AUTO_REFRESH_INTERVAL = 5000;

// ===== LocalStorage Keys =====

/**
 * LocalStorage key constants for session and user data
 */
export const STORAGE_KEYS = {
  sessionId: (userId: number) => `sessionId_${userId}`,
  lastUserId: (tenantId: number) => `lastUserId_tenant_${tenantId}`,
  activeSessionId: (userId: number) => `activeSessionId_user_${userId}`,
  lastTenantId: 'lastTenantId'
} as const;

// ===== File Upload Configuration =====

/**
 * Maximum file size for document uploads (MB)
 */
export const MAX_FILE_SIZE_MB = 10;

/**
 * Maximum file size for document uploads (bytes)
 */
export const MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024;

/**
 * Allowed file types for document uploads
 */
export const ALLOWED_FILE_TYPES = [".pdf", ".txt", ".md"] as const;
