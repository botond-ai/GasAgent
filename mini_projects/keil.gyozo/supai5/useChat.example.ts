/**
 * useChat Hook - Complete Implementation Example
 * 
 * This is a fully working implementation that you can use as-is
 * or modify according to your needs.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type {
  Message,
  UseChatReturn,
  TicketCreateRequest,
  TicketProcessResult,
  WELCOME_MESSAGE,
} from '../types/chat';

const API_URL = 'http://localhost:8000';

/**
 * Main chat hook - manages conversation state and API calls
 */
export function useChat(initialTicketId?: string): UseChatReturn {
  const [ticketId, setTicketId] = useState<string | undefined>(initialTicketId);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hi! I'm your AI support assistant. How can I help you today?",
      timestamp: Date.now(),
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Track if we're currently processing to prevent duplicate calls
  const isProcessingRef = useRef(false);

  /**
   * Create a new ticket with the first message
   */
  const createTicket = useCallback(async (content: string) => {
    if (isProcessingRef.current) return;
    
    isProcessingRef.current = true;
    setIsLoading(true);
    setError(null);

    // 1. Add user message to chat immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      // 2. Create ticket via API
      const ticketData: TicketCreateRequest = {
        customer_name: 'Anonymous User', // TODO: Get from auth context
        customer_email: 'user@example.com', // TODO: Get from auth context
        subject: content.substring(0, 100), // Truncate for subject
        message: content,
      };

      const createResponse = await fetch(`${API_URL}/api/tickets/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(ticketData),
      });

      if (!createResponse.ok) {
        const errorData = await createResponse.json();
        throw new Error(errorData.detail || 'Failed to create ticket');
      }

      const ticket = await createResponse.json();
      setTicketId(ticket.id);

      // 3. Process ticket to get AI response
      const processResponse = await fetch(`${API_URL}/api/tickets/${ticket.id}/process`, {
        method: 'POST',
      });

      if (!processResponse.ok) {
        const errorData = await processResponse.json();
        throw new Error(errorData.detail || 'Failed to process ticket');
      }

      const result: TicketProcessResult = await processResponse.json();

      // 4. Format and add AI response
      const aiContent = formatAIResponse(result.answer_draft);
      const aiMessage: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: aiContent,
        timestamp: Date.now(),
        metadata: {
          category: result.triage.category,
          priority: result.triage.priority,
          sentiment: result.triage.sentiment,
          suggestedTeam: result.triage.suggested_team,
        },
      };

      setMessages((prev) => [...prev, aiMessage]);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      setError(errorMessage);

      // Add error message to chat
      const errorChatMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `⚠️ Error: ${errorMessage}. Please try again.`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorChatMessage]);

    } finally {
      setIsLoading(false);
      isProcessingRef.current = false;
    }
  }, []);

  /**
   * Send a follow-up message to an existing ticket
   * 
   * Note: This is a placeholder for future conversation support
   * Current backend doesn't support multi-turn conversations
   */
  const sendMessage = useCallback(async (content: string) => {
    if (!ticketId) {
      console.warn('No ticket ID - creating new ticket instead');
      return createTicket(content);
    }

    // TODO: Implement when backend supports conversation history
    console.warn('Multi-turn conversations not yet supported');
    
    // For now, just add user message (no API call)
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Add system message explaining limitation
    const systemMessage: Message = {
      id: `system-${Date.now()}`,
      role: 'system',
      content: 'Multi-turn conversations are not yet supported. Each message creates a new ticket.',
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, systemMessage]);

  }, [ticketId, createTicket]);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    ticketId,
    messages,
    isLoading,
    error,
    createTicket,
    sendMessage,
    clearError,
  };
}

/**
 * Format AI answer draft into readable message
 */
function formatAIResponse(draft: { greeting: string; body: string; closing: string }): string {
  return `${draft.greeting}\n\n${draft.body}\n\n${draft.closing}`;
}

/**
 * Alternative: Separate hook for raw API calls
 * Use this if you want more control over the API layer
 */
export function useTicketAPI() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createTicket = useCallback(async (data: TicketCreateRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/tickets/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create ticket');
      }

      return await response.json();

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create ticket';
      setError(errorMessage);
      throw err;

    } finally {
      setIsLoading(false);
    }
  }, []);

  const processTicket = useCallback(async (ticketId: string): Promise<TicketProcessResult> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/tickets/${ticketId}/process`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to process ticket');
      }

      return await response.json();

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process ticket';
      setError(errorMessage);
      throw err;

    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    createTicket,
    processTicket,
    isLoading,
    error,
  };
}
