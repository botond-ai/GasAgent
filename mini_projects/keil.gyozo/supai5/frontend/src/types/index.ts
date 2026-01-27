/**
 * TypeScript type definitions for SupportAI frontend.
 */

export type Priority = 'P1' | 'P2' | 'P3';
export type Sentiment = 'frustrated' | 'neutral' | 'satisfied';
export type Tone = 'empathetic_professional' | 'formal' | 'casual';
export type Compliance = 'passed' | 'failed' | 'warning';
export type TicketStatus = 'new' | 'processing' | 'completed' | 'error';

export interface TriageResult {
  category: string;
  subcategory: string;
  priority: Priority;
  sla_hours: number;
  suggested_team: string;
  sentiment: Sentiment;
  confidence: number;
}

export interface AnswerDraft {
  greeting: string;
  body: string;
  closing: string;
  tone: Tone;
}

export interface Citation {
  text: string;
  source: string;
  relevance: number;
}

export interface PolicyCheck {
  refund_promise: boolean;
  sla_mentioned: boolean;
  escalation_needed: boolean;
  compliance: Compliance;
  notes?: string;
}

export interface TriageResponse {
  ticket_id: string;
  timestamp: string;
  triage: TriageResult;
  answer_draft: AnswerDraft;
  citations: Citation[];
  policy_check: PolicyCheck;
}

export interface Ticket {
  id: string;
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
  created_at: string;
  status: TicketStatus;
  triage_result?: TriageResponse;
}

export interface TicketCreate {
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
}

export interface HealthResponse {
  status: string;
  services: Record<string, string>;
}

// Document types
export interface Document {
  id: string;
  title: string;
  category: string;
  description: string;
  filename: string;
  file_type: string;
  created_at: string;
  chunk_count: number;
}

export interface DocumentChunk {
  chunk_index: number;
  text: string;
}

export interface DocumentDetail extends Document {
  chunks: DocumentChunk[];
}

export interface DocumentStats {
  total_documents: number;
  total_chunks: number;
  categories: Record<string, number>;
  collection_status: string;
}

export interface DocumentCreate {
  file: File;
  title: string;
  category: string;
  description?: string;
}
