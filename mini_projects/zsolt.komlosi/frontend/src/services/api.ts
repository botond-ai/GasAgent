import axios, { AxiosInstance } from 'axios';
import type { ChatRequest, ChatResponse, Document, Session } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 60000, // 60 seconds for RAG processing
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // Chat endpoints
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await this.client.post<{ success: boolean; data: ChatResponse; error?: string }>('/chat', request);
    if (!response.data.success) {
      throw new Error(response.data.error || 'Chat request failed');
    }
    return response.data.data;
  }

  // Session endpoints
  async getSessions(): Promise<Session[]> {
    const response = await this.client.get<Session[]>('/sessions');
    return response.data;
  }

  async getSession(sessionId: string): Promise<Session> {
    const response = await this.client.get<Session>(`/sessions/${sessionId}`);
    return response.data;
  }

  async deleteSession(sessionId: string): Promise<void> {
    await this.client.delete(`/sessions/${sessionId}`);
  }

  // Document endpoints
  async getDocuments(): Promise<Document[]> {
    const response = await this.client.get<{ documents: Document[]; total: number }>('/documents');
    return response.data.documents;
  }

  async uploadDocument(formData: FormData): Promise<Document> {
    const response = await this.client.post<Document>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async indexUrl(url: string, title: string): Promise<Document> {
    const response = await this.client.post<Document>('/documents/index-url', {
      url,
      title,
    });
    return response.data;
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.client.delete(`/documents/${documentId}`);
  }

  async reindexDocument(documentId: string): Promise<Document> {
    const response = await this.client.post<Document>(`/documents/${documentId}/reindex`);
    return response.data;
  }

  // Health check (uses absolute path, not relative to API base URL)
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await axios.get('/health');
    return response.data;
  }
}

export const api = new ApiService();
export default api;
