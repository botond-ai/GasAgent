/**
 * React hook for session-based chat state management.
 * Uses the conversation history API for stateful conversations.
 */
import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../api/client';
import type { Message, Priority, Sentiment } from '../types/chat';

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  content: "Hi! I'm your AI support assistant. How can I help you today?",
  timestamp: Date.now(),
};

// Storage key for session persistence
const SESSION_STORAGE_KEY = 'chat_session_id';

export function useChat(initialSessionId?: string) {
  const [sessionId, setSessionId] = useState<string | undefined>(() => {
    // Try to restore session from localStorage
    if (initialSessionId) return initialSessionId;
    if (typeof window !== 'undefined') {
      return localStorage.getItem(SESSION_STORAGE_KEY) || undefined;
    }
    return undefined;
  });
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load conversation history when session exists
  useEffect(() => {
    if (sessionId) {
      loadHistory(sessionId);
    }
  }, []);

  const loadHistory = async (sid: string) => {
    try {
      const history = await apiClient.getChatHistory(sid);
      if (history.messages.length > 0) {
        const loadedMessages: Message[] = history.messages.map((msg, idx) => ({
          id: `history-${idx}-${Date.now()}`,
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          timestamp: new Date(msg.timestamp).getTime(),
          metadata: msg.metadata as Message['metadata'],
        }));
        setMessages([WELCOME_MESSAGE, ...loadedMessages]);
      }
    } catch (err) {
      // Session might not exist, that's OK
      console.debug('No existing chat history found');
    }
  };

  const resetChat = useCallback(async () => {
    // Clear session from storage
    if (typeof window !== 'undefined') {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }

    // Delete server-side session if exists
    if (sessionId) {
      try {
        await apiClient.deleteChatSession(sessionId);
      } catch (err) {
        // Ignore errors when deleting session
      }
    }

    setSessionId(undefined);
    setMessages([{ ...WELCOME_MESSAGE, timestamp: Date.now() }]);
    setError(null);
  }, [sessionId]);

  const sendMessage = useCallback(async (content: string) => {
    setIsLoading(true);
    setError(null);

    // Add user message immediately (optimistic update)
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      // Send message to chat API
      const response = await apiClient.sendChatMessage(content, sessionId);

      // Store session ID for persistence
      if (response.session_id) {
        setSessionId(response.session_id);
        if (typeof window !== 'undefined') {
          localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
        }
      }

      // Add AI response
      const aiMessage: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: Date.now(),
        metadata: response.metadata ? {
          ticketId: response.metadata.ticket_id,
          category: response.metadata.category,
          priority: response.metadata.priority as Priority | undefined,
          sentiment: response.metadata.sentiment as Sentiment | undefined,
        } : undefined,
      };
      setMessages(prev => [...prev, aiMessage]);

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMsg);

      // Add error message to chat
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Error: ${errorMsg}. Please try again.`,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  return {
    sessionId,
    messages,
    isLoading,
    error,
    sendMessage,
    resetChat,
  };
}
