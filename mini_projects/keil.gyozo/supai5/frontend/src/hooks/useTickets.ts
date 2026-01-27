/**
 * React hook for ticket management.
 */
import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import type { Ticket, TicketCreate, TriageResponse } from '../types';

export const useTickets = () => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadTickets = useCallback(async (status?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listTickets(status);
      setTickets(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tickets');
    } finally {
      setLoading(false);
    }
  }, []);

  const createTicket = useCallback(async (data: TicketCreate): Promise<Ticket | null> => {
    setLoading(true);
    setError(null);
    try {
      const ticket = await apiClient.createTicket(data);
      setTickets(prev => [ticket, ...prev]);
      return ticket;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create ticket');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const processTicket = useCallback(async (ticketId: string): Promise<TriageResponse | null> => {
    setLoading(true);
    setError(null);
    try {
      // Update ticket status to processing
      setTickets(prev =>
        prev.map(t => t.id === ticketId ? { ...t, status: 'processing' as const } : t)
      );

      const result = await apiClient.processTicket(ticketId);

      // Update ticket with result
      setTickets(prev =>
        prev.map(t =>
          t.id === ticketId
            ? { ...t, status: 'completed' as const, triage_result: result }
            : t
        )
      );

      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process ticket');

      // Update ticket status to error
      setTickets(prev =>
        prev.map(t => t.id === ticketId ? { ...t, status: 'error' as const } : t)
      );

      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteTicket = useCallback(async (ticketId: string): Promise<boolean> => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.deleteTicket(ticketId);
      setTickets(prev => prev.filter(t => t.id !== ticketId));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete ticket');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  return {
    tickets,
    loading,
    error,
    loadTickets,
    createTicket,
    processTicket,
    deleteTicket,
  };
};
