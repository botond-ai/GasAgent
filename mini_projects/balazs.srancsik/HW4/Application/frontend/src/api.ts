/**
 * API client for backend communication.
 */
import axios from 'axios';
import { ChatRequest, ChatResponse } from './types';

const API_BASE_URL = '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/chat', request);
    return response.data;
  },

  async sendMessageWithFiles(
    userId: string,
    message: string,
    sessionId: string | undefined,
    files: File[]
  ): Promise<ChatResponse> {
    const formData = new FormData();
    formData.append('user_id', userId);
    formData.append('message', message);
    if (sessionId) {
      formData.append('session_id', sessionId);
    }
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await apiClient.post<ChatResponse>('/chat/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async getSession(sessionId: string) {
    const response = await apiClient.get(`/session/${sessionId}`);
    return response.data;
  },

  async getProfile(userId: string) {
    const response = await apiClient.get(`/profile/${userId}`);
    return response.data;
  },

  async updateProfile(userId: string, updates: any) {
    const response = await apiClient.put(`/profile/${userId}`, updates);
    return response.data;
  },

  async searchHistory(query: string) {
    const response = await apiClient.get('/history/search', {
      params: { q: query },
    });
    return response.data;
  },
};
