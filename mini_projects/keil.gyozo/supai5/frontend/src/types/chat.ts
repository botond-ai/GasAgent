/**
 * TypeScript type definitions for chat interface.
 */

import type { Priority, Sentiment } from './index';

export type { Priority, Sentiment };

export type MessageRole = 'user' | 'assistant' | 'system';

export interface MessageMetadata {
  ticketId?: string;
  category?: string;
  priority?: Priority;
  sentiment?: Sentiment;
  suggestedTeam?: string;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  metadata?: MessageMetadata;
}

export type ConversationStatus = 'active' | 'resolved' | 'waiting';

export interface Conversation {
  ticketId: string;
  messages: Message[];
  status: ConversationStatus;
}

export interface ToolCall {
  name: string;
  status: 'pending' | 'success' | 'error';
  duration?: string;
  output?: Record<string, unknown>;
}

export interface DebugState {
  toolCalls: ToolCall[];
  memory: Record<string, unknown>;
  logs: string[];
}
