export interface Tenant {
  tenant_id: number;
  key: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  description?: string;
  system_prompt?: string;
  settings?: any;
}

export interface User {
  user_id: number;
  tenant_id?: number;
  firstname: string;
  lastname: string;
  nickname: string;
  email: string;
  role: string;
  is_active: boolean;
  default_lang?: string;
  system_prompt?: string;
  created_at: string;
}

export interface Message {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp: string;
  sources?: {id: number; title: string}[];
  responseTime?: number; // milliseconds
  metadata?: {
    execution_id?: string; // NEW: Workflow execution tracking
    sources?: {id: number; title: string}[];
    actions_taken?: string[];
    workflow_path?: string;
  };
  ragParams?: {
    top_k: number;
    min_score_threshold: number;
  };
  promptDetails?: {
    system_prompt?: string;
    chat_history?: any[];
    current_query?: string;
    system_prompt_cached?: boolean;
    cache_source?: string;
    user_firstname?: string;
    user_lastname?: string;
    user_email?: string;
    user_role?: string;
    user_language?: string;
    chat_history_count?: number;
    actions_taken?: string[];
    short_term_memory_messages?: number;
    short_term_memory_scope?: string;
    actual_llm_messages?: {
      type: string;
      content: string;
    }[];
  };
}

export interface ChatRequest {
  user_id: number;
  tenant_id: number;
  session_id: string;
  message: string;
}

export interface ChatResponse {
  answer: string;
  sources?: {id: number; title: string}[];
  error?: string | null;
  execution_id?: string; // NEW: Workflow execution tracking
  rag_params?: {
    top_k: number;
    min_score_threshold: number;
  };
  prompt_details?: {
    system_prompt?: string;
    chat_history?: any[];
    current_query?: string;
    system_prompt_cached?: boolean;
    cache_source?: string;
    user_firstname?: string;
    user_lastname?: string;
    user_email?: string;
    user_role?: string;
    user_language?: string;
    chat_history_count?: number;
    actions_taken?: string[];
    short_term_memory_messages?: number;
    short_term_memory_scope?: string;
    actual_llm_messages?: {
      type: string;
      content: string;
    }[];
  };
}

export interface MessageExchange {
  timestamp: string;
  user_message: string;
  assistant_message: string | null;
}

export interface Document {
  id: number;
  tenant_id: number;
  user_id: number | null;
  visibility: 'private' | 'tenant';
  source: string;
  title: string;
  created_at: string;
}

export interface DocumentSummary {
  id: number;
  tenant_id: number;
  user_id: number | null;
  owner_id: number;
  owner_nickname: string;
  visibility: 'private' | 'tenant';
  source: string;
  title: string;
  content_preview?: string;
  content_length?: number;
  chunk_count?: number;
  uploaded_at: string;
  created_at: string;
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
  count: number;
}

export interface LongTermMemory {
  id: number;
  user_id: number;
  tenant_id: number;
  memory_type: 'session_summary' | 'explicit_fact';
  content: string;
  source: string;
  qdrant_point_id: string | null;
  created_at: string;
}

export interface LangGraphMessage {
  type: 'system' | 'human' | 'ai';
  content: string;
  timestamp?: string;
}

export interface LangGraphState {
  messages: LangGraphMessage[];
  user_context: {
    user_id: number;
    tenant_id: number;
    nickname: string;
    firstname: string;
    lastname: string;
    role: string;
    default_lang: string;
  };
  total_messages: number;
}

export interface DocumentChunk {
  chunk_id: number;
  document_id: number;
  content: string;
  metadata: Record<string, any>;
  similarity_score: number;
}

export interface RAGWorkflowState {
  query: string | null;
  user_context: Record<string, any>;
  system_prompt: string | null;
  combined_prompt: string | null;
  needs_rag: boolean;
  retrieved_chunks: DocumentChunk[];
  has_relevant_context: boolean;
  final_answer: string | null;
  sources: number[];
  error: string | null;
}

export interface DocumentProcessingState {
  filename: string | null;
  file_type: string | null;
  tenant_id: number | null;
  user_id: number | null;
  visibility: string | null;
  extracted_text: string | null;
  document_id: number | null;
  chunk_ids: number[];
  embedding_count: number;
  qdrant_point_ids: string[];
  status: string;
  error: string | null;
  processing_summary: Record<string, any>;
}

export interface SessionMemoryState {
  session_id: string | null;
  tenant_id: number | null;
  user_id: number | null;
  session_data: Record<string, any> | null;
  interactions: any[];
  interaction_count: number;
  needs_summary: boolean;
  summary_text: string | null;
  embedding_vector: number[] | null;
  qdrant_point_id: string | null;
  ltm_id: number | null;
  status: string;
  error: string | null;
  processing_summary: Record<string, any>;
}

export interface AllWorkflowStates {
  chat: LangGraphState;
  rag: RAGWorkflowState;
  document_processing: DocumentProcessingState;
  session_memory: SessionMemoryState;
}

export interface DebugInfo {
  user_data: User;
  last_exchanges: MessageExchange[];
  accessible_documents: Document[];
  workflow_states: AllWorkflowStates;
}

// Workflow Execution Types (for visualization)
export interface NodeExecution {
  node_execution_id: number;
  execution_id: string;
  node_name: string;
  node_index: number;
  started_at: string;
  completed_at: string | null;
  duration_ms: number;
  status: "success" | "error" | "skipped";
  error_message: string | null;
  state_before: Record<string, any> | null;
  state_after: Record<string, any> | null;
  state_diff: Record<string, any> | null;
  metadata: Record<string, any> | null;
  parent_node: string | null; // Hierarchy: indicates this is a child node
}

export interface WorkflowExecution {
  execution_id: string;
  session_id: string;
  tenant_id: number;
  user_id: number;
  query: string;
  query_rewritten: string | null;
  query_intent: string | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number;
  status: "in_progress" | "completed" | "failed";
  final_answer: string | null;
  error_message: string | null;
  total_nodes_executed: number;
  iteration_count: number;
  reflection_count: number;
  tools_called: string[] | null;
  final_state: Record<string, any> | null;
  llm_tokens_total: number;
  llm_cost_usd: number;
  request_id: string | null;
  trace_id: string | null;
}

