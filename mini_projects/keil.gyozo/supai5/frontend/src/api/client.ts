/**
 * API client for SupportAI backend.
 */
import axios, { AxiosInstance } from 'axios';
import type {
  Ticket,
  TicketCreate,
  TriageResponse,
  HealthResponse,
  Document,
  DocumentDetail,
  DocumentStats,
} from '../types';

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: '/api',
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 60000, // 60 seconds for AI processing
    });
  }

  // Health endpoints
  async healthCheck(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/health');
    return response.data;
  }

  // Ticket endpoints
  async createTicket(data: TicketCreate): Promise<Ticket> {
    const response = await this.client.post<Ticket>('/tickets/', data);
    return response.data;
  }

  async listTickets(status?: string, limit: number = 50): Promise<Ticket[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('limit', limit.toString());

    const response = await this.client.get<Ticket[]>(`/tickets/?${params.toString()}`);
    return response.data;
  }

  async getTicket(ticketId: string): Promise<Ticket> {
    const response = await this.client.get<Ticket>(`/tickets/${ticketId}`);
    return response.data;
  }

  async processTicket(ticketId: string): Promise<TriageResponse> {
    const response = await this.client.post<TriageResponse>(
      `/tickets/${ticketId}/process`
    );
    return response.data;
  }

  async deleteTicket(ticketId: string): Promise<void> {
    await this.client.delete(`/tickets/${ticketId}`);
  }

  // Document endpoints
  async listDocuments(category?: string, limit: number = 100): Promise<Document[]> {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    params.append('limit', limit.toString());

    const response = await this.client.get<Document[]>(`/documents/?${params.toString()}`);
    return response.data;
  }

  async getDocument(docId: string): Promise<DocumentDetail> {
    const response = await this.client.get<DocumentDetail>(`/documents/${docId}`);
    return response.data;
  }

  async uploadDocument(
    file: File,
    title: string,
    category: string,
    description?: string
  ): Promise<{ success: boolean; message: string; document: Document }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('category', category);
    if (description) {
      formData.append('description', description);
    }

    const response = await this.client.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async deleteDocument(docId: string): Promise<void> {
    await this.client.delete(`/documents/${docId}`);
  }

  async getDocumentStats(): Promise<DocumentStats> {
    const response = await this.client.get<DocumentStats>('/documents/stats');
    return response.data;
  }

  // Chat endpoints
  async sendChatMessage(
    content: string,
    sessionId?: string
  ): Promise<{
    session_id: string;
    message: string;
    metadata?: {
      ticket_id?: string;
      category?: string;
      priority?: string;
      sentiment?: string;
    };
  }> {
    const response = await this.client.post('/chat/message', {
      content,
      session_id: sessionId,
    });
    return response.data;
  }

  async getChatHistory(
    sessionId: string,
    lastN?: number
  ): Promise<{
    session_id: string;
    messages: Array<{
      role: string;
      content: string;
      timestamp: string;
      metadata?: Record<string, unknown>;
    }>;
  }> {
    const params = lastN ? `?last_n=${lastN}` : '';
    const response = await this.client.get(`/chat/history/${sessionId}${params}`);
    return response.data;
  }

  async createChatSession(
    userId?: string,
    context?: Record<string, unknown>
  ): Promise<{ session_id: string; created: boolean }> {
    const response = await this.client.post('/chat/session', {
      user_id: userId,
      context,
    });
    return response.data;
  }

  async deleteChatSession(sessionId: string): Promise<void> {
    await this.client.delete(`/chat/session/${sessionId}`);
  }
}

export const apiClient = new APIClient();
