import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Message, Session, ChatResponse } from '../types';
import api from '../services/api';

interface ChatState {
  // State
  messages: Message[];
  sessions: Session[];
  currentSessionId: string | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
  setCurrentSession: (sessionId: string | null) => void;
  loadSessions: () => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  clearError: () => void;
}

const generateMessageId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      sessions: [],
      currentSessionId: null,
      isLoading: false,
      error: null,

      sendMessage: async (content: string) => {
        const userMessage: Message = {
          id: generateMessageId(),
          role: 'user',
          content,
          timestamp: new Date(),
        };

        // Add user message and loading indicator
        set((state) => ({
          messages: [
            ...state.messages,
            userMessage,
            {
              id: generateMessageId(),
              role: 'assistant',
              content: '',
              timestamp: new Date(),
              isLoading: true,
            },
          ],
          isLoading: true,
          error: null,
        }));

        try {
          const response: ChatResponse = await api.sendMessage({
            message: content,
            session_id: get().currentSessionId || undefined,
          });

          // Update session ID if new
          if (!get().currentSessionId) {
            set({ currentSessionId: response.session_id });
          }

          // Format the response message
          const formattedBody = formatAnswerDraft(response);

          const assistantMessage: Message = {
            id: generateMessageId(),
            role: 'assistant',
            content: formattedBody,
            timestamp: new Date(),
            citations: response.citations,
            triage: response.triage,
          };

          // Remove loading message and add actual response
          set((state) => ({
            messages: [...state.messages.filter((m) => !m.isLoading), assistantMessage],
            isLoading: false,
          }));
        } catch (error) {
          // Remove loading message on error
          set((state) => ({
            messages: state.messages.filter((m) => !m.isLoading),
            isLoading: false,
            error: error instanceof Error ? error.message : 'Hiba történt a feldolgozás során',
          }));
        }
      },

      clearMessages: () => {
        set({
          messages: [],
          currentSessionId: null,
        });
      },

      setCurrentSession: (sessionId: string | null) => {
        set({
          currentSessionId: sessionId,
          messages: [],
        });
      },

      loadSessions: async () => {
        try {
          const sessions = await api.getSessions();
          set({ sessions });
        } catch (error) {
          console.error('Failed to load sessions:', error);
        }
      },

      deleteSession: async (sessionId: string) => {
        try {
          await api.deleteSession(sessionId);
          set((state) => ({
            sessions: state.sessions.filter((s) => s.id !== sessionId),
            currentSessionId: state.currentSessionId === sessionId ? null : state.currentSessionId,
            messages: state.currentSessionId === sessionId ? [] : state.messages,
          }));
        } catch (error) {
          console.error('Failed to delete session:', error);
        }
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'supportai-chat-storage',
      partialize: (state) => ({
        currentSessionId: state.currentSessionId,
      }),
    }
  )
);

// Helper function to format answer draft
function formatAnswerDraft(response: ChatResponse): string {
  const { answer_draft, citations } = response;

  let body = `${answer_draft.greeting}\n\n${answer_draft.body}\n\n${answer_draft.closing}`;

  // Add citation references if present
  if (citations && citations.length > 0) {
    body += '\n\n---\n**Források:**\n';
    citations.forEach((citation) => {
      body += `[${citation.id}] ${citation.title} (relevancia: ${Math.round(citation.score * 100)}%)\n`;
    });
  }

  return body;
}

export default useChatStore;
