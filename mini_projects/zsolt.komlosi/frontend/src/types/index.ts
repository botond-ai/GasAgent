// API Response Types
export interface Triage {
  category: string;
  subcategory?: string;
  priority: 'P1' | 'P2' | 'P3' | 'P4';
  sla_hours: number;
  suggested_team: string;
  sentiment: 'frustrated' | 'neutral' | 'satisfied';
  confidence: number;
}

export interface AnswerDraft {
  greeting: string;
  body: string;
  closing: string;
  tone: string;
}

export interface Citation {
  id: number;
  doc_id: string;
  title: string;
  excerpt: string;
  score: number;
}

export interface PolicyCheck {
  refund_promise: boolean;
  sla_mentioned: boolean;
  escalation_needed: boolean;
  compliance: 'passed' | 'warning' | 'failed';
}

export interface ChatResponse {
  session_id: string;
  triage: Triage;
  answer_draft: AnswerDraft;
  citations: Citation[];
  policy_check: PolicyCheck;
  processing_time_ms?: number;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  ip_address?: string;
}

// Chat UI Types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  triage?: Triage;
  isLoading?: boolean;
}

export interface Session {
  id: string;
  created_at: Date;
  updated_at: Date;
  message_count: number;
  summary?: string;
}

// Document Types
export interface Document {
  id: string;
  title: string;
  source_type: 'markdown' | 'pdf' | 'docx' | 'confluence' | 'web';
  source_path: string;
  chunk_count: number;
  indexed_at: Date;
  metadata?: Record<string, unknown>;
}

export interface DocumentUploadRequest {
  title: string;
  content?: string;
  url?: string;
  file?: File;
}

// Ticket Types (for Jira integration)
export interface Ticket {
  id: string;
  jira_key?: string;
  subject: string;
  description: string;
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  priority: 'P1' | 'P2' | 'P3' | 'P4';
  created_at: Date;
  updated_at: Date;
  analysis?: Triage;
}

// Priority configuration
export const PRIORITY_CONFIG = {
  P1: { label: 'Kritikus', color: 'red', slaHours: 4 },
  P2: { label: 'Magas', color: 'orange', slaHours: 8 },
  P3: { label: 'Közepes', color: 'yellow', slaHours: 24 },
  P4: { label: 'Alacsony', color: 'green', slaHours: 72 },
} as const;

// Sentiment configuration
export const SENTIMENT_CONFIG = {
  frustrated: { label: 'Frusztrált', color: 'red', icon: '😤' },
  neutral: { label: 'Semleges', color: 'gray', icon: '😐' },
  satisfied: { label: 'Elégedett', color: 'green', icon: '😊' },
} as const;
