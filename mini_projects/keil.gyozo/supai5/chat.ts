/**
 * TypeScript type definitions for ChatGPT-style ticket interface
 * 
 * Usage:
 * Import these types in your components and hooks
 * 
 * @example
 * import type { Message, Conversation, TriageMetadata } from './types/chat';
 */

// ============================================================================
// Message Types
// ============================================================================

/**
 * Message role - who sent the message
 */
export type MessageRole = 'user' | 'assistant' | 'system';

/**
 * Priority levels from AI triage
 */
export type Priority = 'P1' | 'P2' | 'P3';

/**
 * Customer sentiment from AI analysis
 */
export type Sentiment = 'frustrated' | 'neutral' | 'satisfied';

/**
 * Triage metadata attached to AI messages
 */
export interface TriageMetadata {
  category: string;
  priority: Priority;
  sentiment: Sentiment;
  suggestedTeam: string;
}

/**
 * Individual chat message
 */
export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  metadata?: TriageMetadata;
}

// ============================================================================
// Conversation Types
// ============================================================================

/**
 * Conversation status
 */
export type ConversationStatus = 'active' | 'resolved' | 'waiting';

/**
 * Complete conversation with ticket
 */
export interface Conversation {
  ticketId: string;
  messages: Message[];
  status: ConversationStatus;
  createdAt: number;
  updatedAt: number;
}

// ============================================================================
// API Request/Response Types
// ============================================================================

/**
 * Ticket creation request
 */
export interface TicketCreateRequest {
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
}

/**
 * Ticket creation response
 */
export interface TicketCreateResponse {
  id: string;
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
  status: string;
  created_at: string;
}

/**
 * AI answer draft structure
 */
export interface AnswerDraft {
  greeting: string;
  body: string;
  closing: string;
}

/**
 * AI triage response structure
 */
export interface TriageResponse {
  category: string;
  priority: Priority;
  sentiment: Sentiment;
  suggested_team: string;
}

/**
 * Ticket processing result
 */
export interface TicketProcessResult {
  triage: TriageResponse;
  answer_draft: AnswerDraft;
}

// ============================================================================
// Debug Panel Types
// ============================================================================

/**
 * Tool call status
 */
export type ToolStatus = 'pending' | 'success' | 'error';

/**
 * Individual tool call record
 */
export interface ToolCall {
  id: string;
  name: string;
  status: ToolStatus;
  duration: number; // milliseconds
  timestamp: number;
  input?: unknown;
  output?: unknown;
  error?: string;
}

/**
 * Workflow memory snapshot
 */
export interface WorkflowMemory {
  preferences: {
    language?: string;
    tone?: string;
    [key: string]: unknown;
  };
  workflowState: {
    intent?: string;
    category?: string;
    priority?: Priority;
    [key: string]: unknown;
  };
}

/**
 * Log entry
 */
export interface LogEntry {
  id: string;
  level: 'info' | 'warn' | 'error';
  message: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

// ============================================================================
// Component Props Types
// ============================================================================

/**
 * ChatContainer component props
 */
export interface ChatContainerProps {
  ticketId?: string;
  showDebug?: boolean;
  onTicketCreated?: (ticketId: string) => void;
  className?: string;
}

/**
 * MessageList component props
 */
export interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
  className?: string;
}

/**
 * MessageBubble component props
 */
export interface MessageBubbleProps {
  message: Message;
  showMetadata?: boolean;
  className?: string;
}

/**
 * InputBar component props
 */
export interface InputBarProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

/**
 * TypingIndicator component props
 */
export interface TypingIndicatorProps {
  className?: string;
}

/**
 * DebugPanel component props
 */
export interface DebugPanelProps {
  isOpen?: boolean;
  onToggle?: () => void;
  toolCalls?: ToolCall[];
  memory?: WorkflowMemory;
  logs?: LogEntry[];
  className?: string;
}

// ============================================================================
// Hook Return Types
// ============================================================================

/**
 * useChat hook return type
 */
export interface UseChatReturn {
  ticketId: string | undefined;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  createTicket: (content: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  clearError: () => void;
}

/**
 * useTicketAPI hook return type
 */
export interface UseTicketAPIReturn {
  createTicket: (data: TicketCreateRequest) => Promise<TicketCreateResponse>;
  processTicket: (ticketId: string) => Promise<TicketProcessResult>;
  isLoading: boolean;
  error: string | null;
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * API error response
 */
export interface APIError {
  detail: string;
  status?: number;
}

/**
 * Formatted timestamp
 */
export type FormattedTimestamp = string; // e.g., "2:30 PM" or "Yesterday, 3:45 PM"

/**
 * Chat state
 */
export interface ChatState {
  conversation: Conversation | null;
  isLoading: boolean;
  error: string | null;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Default welcome message
 */
export const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  content: "Hi! I'm your AI support assistant. How can I help you today?",
  timestamp: Date.now(),
};

/**
 * API endpoints
 */
export const API_ENDPOINTS = {
  CREATE_TICKET: '/api/tickets/',
  PROCESS_TICKET: (ticketId: string) => `/api/tickets/${ticketId}/process`,
  GET_TICKET: (ticketId: string) => `/api/tickets/${ticketId}`,
  LIST_TICKETS: '/api/tickets/',
} as const;

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Check if message is from user
 */
export function isUserMessage(message: Message): boolean {
  return message.role === 'user';
}

/**
 * Check if message is from assistant
 */
export function isAssistantMessage(message: Message): boolean {
  return message.role === 'assistant';
}

/**
 * Check if message has metadata
 */
export function hasMetadata(message: Message): message is Message & { metadata: TriageMetadata } {
  return message.metadata !== undefined;
}

/**
 * Check if tool call was successful
 */
export function isSuccessfulToolCall(toolCall: ToolCall): boolean {
  return toolCall.status === 'success';
}
