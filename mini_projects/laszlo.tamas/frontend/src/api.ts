import { User, ChatRequest, ChatResponse, Message, DebugInfo, Tenant, LongTermMemory, DocumentListResponse, WorkflowExecution, NodeExecution } from "./types";
import { API_BASE_URL } from "./config/constants";

// ===== Public Configuration Types =====
export interface FileUploadConfig {
  max_file_size_mb: number;
  allowed_file_types: string[];
}

export interface PublicConfig {
  app_version: string;
  file_upload: FileUploadConfig;
}

// Cached public config
let cachedPublicConfig: PublicConfig | null = null;

/**
 * Fetch public configuration from backend.
 * Cached after first call to avoid repeated requests.
 */
export async function getPublicConfig(): Promise<PublicConfig> {
  if (cachedPublicConfig !== null) {
    return cachedPublicConfig;
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/config`);
    if (!response.ok) {
      console.warn('Failed to fetch public config, using defaults');
      cachedPublicConfig = {
        app_version: "0.0.0",
        file_upload: {
          max_file_size_mb: 10,
          allowed_file_types: [".pdf", ".txt", ".md"]
        }
      };
      return cachedPublicConfig;
    }
    cachedPublicConfig = await response.json();
    console.log(`📋 Public config loaded: v${cachedPublicConfig!.app_version}, max file: ${cachedPublicConfig!.file_upload.max_file_size_mb}MB`);
    return cachedPublicConfig!;
  } catch (error) {
    console.warn('Error fetching public config:', error);
    cachedPublicConfig = {
      app_version: "0.0.0",
      file_upload: {
        max_file_size_mb: 10,
        allowed_file_types: [".pdf", ".txt", ".md"]
      }
    };
    return cachedPublicConfig;
  }
}

// Runtime dev mode status (fetched from backend system.ini)
let cachedDevMode: boolean | null = null;

/**
 * Fetch dev mode status from backend (system.ini [development] DEV_MODE).
 * Cached after first call to avoid repeated requests.
 */
export async function getDevMode(): Promise<boolean> {
  if (cachedDevMode !== null) {
    return cachedDevMode;
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/admin/config/dev-mode`);
    if (!response.ok) {
      console.warn('Failed to fetch dev-mode, defaulting to false');
      cachedDevMode = false;
      return false;
    }
    const data = await response.json();
    cachedDevMode = data.dev_mode as boolean;
    console.log(`🔧 Dev mode (from system.ini): ${cachedDevMode}`);
    return cachedDevMode;
  } catch (error) {
    console.warn('Error fetching dev-mode:', error);
    cachedDevMode = false;
    return false;
  }
}

/**
 * Get default fetch headers with optional cache control for dev mode.
 * Dev mode is fetched from backend at runtime (system.ini).
 */
async function getDefaultHeaders(): Promise<HeadersInit> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  
  // Disable cache in dev mode (fetched from backend)
  const devMode = await getDevMode();
  if (devMode) {
    headers["Cache-Control"] = "no-cache, no-store, must-revalidate";
    headers["Pragma"] = "no-cache";
    headers["Expires"] = "0";
  }
  
  return headers;
}

export async function fetchTenants(activeOnly: boolean = true): Promise<Tenant[]> {
  const response = await fetch(`${API_BASE_URL}/tenants?active_only=${activeOnly}`, {
    headers: await getDefaultHeaders(),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch tenants");
  }
  return response.json();
}

export async function fetchUsers(tenantId?: number): Promise<User[]> {
  const url = tenantId 
    ? `${API_BASE_URL}/users?tenant_id=${tenantId}`
    : `${API_BASE_URL}/users`;
  const response = await fetch(url, {
    headers: await getDefaultHeaders(),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch users");
  }
  return response.json();
}

/**
 * Warm up caches for a user (tenant, user, system prompt).
 * Called when user is selected from dropdown to eliminate cold start.
 * 
 * Performance: 800-1200ms first time (LLM generation), 2-5ms subsequent calls (cache hits).
 */
export async function warmupCaches(tenantId: number, userId: number): Promise<{
  success: boolean;
  tenant_cached: boolean;
  user_cached: boolean;
  system_prompt_cached: boolean;
  cache_source: string;
  total_time_ms: number;
}> {
  try {
    const response = await fetch(`${API_BASE_URL}/cache/warmup`, {
      method: "POST",
      headers: await getDefaultHeaders(),
      body: JSON.stringify({
        tenant_id: tenantId,
        user_id: userId
      }),
    });
    
    if (!response.ok) {
      console.warn('Cache warmup failed (non-blocking):', response.status);
      return {
        success: false,
        tenant_cached: false,
        user_cached: false,
        system_prompt_cached: false,
        cache_source: "failed",
        total_time_ms: 0
      };
    }
    
    const result = await response.json();
    console.log(`🔥 Cache warmup: ${result.total_time_ms}ms (${result.cache_source})`);
    return result;
  } catch (error) {
    console.warn('Cache warmup error (non-blocking):', error);
    return {
      success: false,
      tenant_cached: false,
      user_cached: false,
      system_prompt_cached: false,
      cache_source: "error",
      total_time_ms: 0
    };
  }
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: await getDefaultHeaders(),
    body: JSON.stringify({
      query: request.message,
      session_id: request.session_id,
      user_context: {
        tenant_id: request.tenant_id,
        user_id: request.user_id
      }
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to send message");
  }
  
  return response.json();
}

export async function fetchSessionMessages(sessionId: string, userId: number): Promise<Message[]> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages?user_id=${userId}`, {
    headers: await getDefaultHeaders(),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch session messages");
  }
  const data = await response.json();
  const messages = data.messages || [];
  return messages.map((msg: any) => ({
    role: msg.role,
    content: msg.content,
    timestamp: msg.created_at,
    sources: msg.metadata?.sources || [],
    ragParams: msg.metadata?.rag_params || null,
    metadata: {
      execution_id: msg.metadata?.execution_id, // NEW: Include execution_id from stored metadata
    },
  }));
}

export async function fetchDebugInfo(userId: number, tenantId: number): Promise<DebugInfo> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}/debug?tenant_id=${tenantId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch debug information");
  }
  return response.json();
}

export async function deleteUserConversations(userId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}/conversations`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to delete conversation history");
  }
}

export async function resetPostgres(): Promise<{ status: string; documents_deleted: number; chunks_deleted: number }> {
  const response = await fetch(`${API_BASE_URL}/debug/reset/postgres`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to reset PostgreSQL");
  }
  return response.json();
}

export async function resetQdrant(): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/debug/reset/qdrant`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to reset Qdrant");
  }
  return response.json();
}

export async function resetCache(): Promise<{ memory_cleared: boolean; db_cleared: number; error?: string }> {
  const response = await fetch(`${API_BASE_URL}/admin/cache/clear`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to reset cache");
  }
  return response.json();
}

export async function updateUser(userId: number, updates: Partial<User>): Promise<{ success: boolean; user: User }> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to update user");
  }
  return response.json();
}

export async function updateTenant(tenantId: number, updates: Partial<Tenant>): Promise<{ success: boolean; tenant: Tenant }> {
  const response = await fetch(`${API_BASE_URL}/tenants/${tenantId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to update tenant");
  }
  return response.json();
}

// ============================================================================
// P0.17 - Cache Control API
// ============================================================================

export interface CacheStats {
  memory_cache: {
    enabled: boolean;
    size: number;
    keys: string[];
    ttl_seconds: number;
    debug_mode: boolean;
  };
  db_cache: {
    enabled: boolean;
    cached_users: number;
    total_entries: number;
    error?: string;
  };
  config: {
    memory_enabled: boolean;
    db_enabled: boolean;
    browser_enabled: boolean;
    llm_enabled: boolean;
  };
  timestamp: string;
}

export async function getCacheStats(): Promise<CacheStats> {
  const response = await fetch(`${API_BASE_URL}/admin/cache/stats`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to get cache stats");
  }
  return response.json();
}

export async function clearAllCaches(): Promise<{ memory_cleared: boolean; db_cleared: number }> {
  const response = await fetch(`${API_BASE_URL}/admin/cache/clear`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to clear caches");
  }
  return response.json();
}

/**
 * Consolidate session STM → LTM
 * Extracts key facts from session messages and stores in long_term_memories.
 */
export async function consolidateSession(
  sessionId: string,
  userId: number,
  tenantId: number
): Promise<{ status: string; facts_extracted: number; message: string }> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/consolidate`, {
    method: "POST",
    headers: await getDefaultHeaders(),
    body: JSON.stringify({
      user_context: {
        tenant_id: tenantId,
        user_id: userId
      }
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to consolidate session");
  }
  return response.json();
}

/**
 * Fetch idle timeout configuration from backend
 */
export async function fetchIdleTimeout(): Promise<{ idle_timeout_seconds: number }> {
  const response = await fetch(`${API_BASE_URL}/admin/config/idle-timeout`, {
    headers: await getDefaultHeaders(),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch idle timeout config");
  }
  return response.json();
}

export async function invalidateUserCache(userId: number): Promise<{ user_id: number; memory_cleared: number; db_cleared: number }> {
  const response = await fetch(`${API_BASE_URL}/admin/cache/user/${userId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to invalidate user cache");
  }
  return response.json();
}

export async function invalidateTenantCache(tenantId: number): Promise<{ tenant_id: number; users_affected: number; memory_cleared: number; db_cleared: number }> {
  const response = await fetch(`${API_BASE_URL}/admin/cache/tenant/${tenantId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to invalidate tenant cache");
  }
  return response.json();
}

export async function fetchLongTermMemories(
  userId: number, 
  limit: number = 50
): Promise<{ memories: LongTermMemory[]; count: number }> {
  const response = await fetch(
    `${API_BASE_URL}/users/${userId}/memories?limit=${Math.min(limit, 100)}`,
    {
      headers: await getDefaultHeaders(),
    }
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to fetch long-term memories");
  }
  return response.json();
}

export async function listDocuments(
  userId: number,
  tenantId: number
): Promise<DocumentListResponse> {
  const response = await fetch(
    `${API_BASE_URL}/documents?user_id=${userId}&tenant_id=${tenantId}`,
    {
      headers: await getDefaultHeaders(),
    }
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to list documents");
  }
  return response.json();
}

/**
 * Delete a document by ID (with permission check).
 * 
 * Backend enforces permission via FastAPI dependency:
 * - Document must belong to same tenant
 * - Private documents: only owner can delete
 * - Tenant-wide documents: any user in tenant can delete (for now)
 * 
 * @param documentId - ID of the document to delete
 * @param userId - ID of the user requesting deletion
 * @param tenantId - ID of the tenant the user belongs to
 * @returns Success confirmation
 * @throws Error if permission denied (403) or document not found (404)
 */
export async function deleteDocument(
  documentId: number,
  userId: number,
  tenantId: number
): Promise<{ status: string; message: string; document_id: number }> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${documentId}?user_id=${userId}&tenant_id=${tenantId}`,
    {
      method: "DELETE",
      headers: await getDefaultHeaders(),
    }
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to delete document");
  }
  return response.json();
}

/**
 * Fetch workflow execution details by execution ID.
 * Used to visualize workflow graph when user clicks on an LLM message.
 * 
 * @param executionId - UUID of the workflow execution
 * @returns Workflow execution metadata
 * @throws Error if execution not found (404) or API error
 */
export async function fetchWorkflowExecution(executionId: string): Promise<WorkflowExecution> {
  const response = await fetch(`${API_BASE_URL}/workflow-executions/${executionId}`, {
    headers: await getDefaultHeaders(),
  });
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Workflow execution not found");
    }
    throw new Error("Failed to fetch workflow execution");
  }
  return response.json();
}

/**
 * Fetch node execution traces for a workflow execution.
 * Returns all nodes executed in order with their input/output states.
 * 
 * @param executionId - UUID of the workflow execution
 * @returns Array of node executions (ordered by node_index)
 * @throws Error if execution not found (404) or API error
 */
export async function fetchNodeExecutions(executionId: string): Promise<NodeExecution[]> {
  const response = await fetch(`${API_BASE_URL}/workflow-executions/${executionId}/nodes`, {
    headers: await getDefaultHeaders(),
  });
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Node executions not found");
    }
    throw new Error("Failed to fetch node executions");
  }
  return response.json();
}

