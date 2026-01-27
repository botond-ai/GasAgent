/**
 * Tickets page with sidebar layout.
 * Left: Ticket list, Right: Detail view or new ticket form
 */
import { useState } from 'react';
import { useTickets } from '../hooks/useTickets';
import { TicketList } from '../components/tickets/TicketList';
import { TicketDetail } from '../components/tickets/TicketDetail';
import { NewTicketForm } from '../components/tickets/NewTicketForm';
import type { TicketCreate } from '../types';
import '../styles/components.css';

export default function Tickets() {
  const {
    tickets,
    loading,
    error,
    createTicket,
    processTicket,
    deleteTicket,
  } = useTickets();

  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [showNewTicketForm, setShowNewTicketForm] = useState(false);
  const [processing, setProcessing] = useState(false);

  const selectedTicket = tickets.find((t) => t.id === selectedTicketId) || null;

  const handleCreateTicket = async (data: TicketCreate) => {
    const ticket = await createTicket(data);
    if (ticket) {
      setShowNewTicketForm(false);
      setSelectedTicketId(ticket.id);
    }
  };

  const handleProcessTicket = async (ticketId: string) => {
    setProcessing(true);
    try {
      await processTicket(ticketId);
    } finally {
      setProcessing(false);
    }
  };

  const handleDeleteTicket = async (ticketId: string) => {
    if (window.confirm('Are you sure you want to delete this ticket?')) {
      const success = await deleteTicket(ticketId);
      if (success && selectedTicketId === ticketId) {
        setSelectedTicketId(null);
      }
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Support Tickets</h1>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <div className="sidebar-header">
            <h2>Tickets</h2>
            <button
              className="btn btn-primary"
              onClick={() => {
                setShowNewTicketForm(true);
                setSelectedTicketId(null);
              }}
              style={{ width: '100%' }}
            >
              + New Ticket
            </button>
          </div>
          <TicketList
            tickets={tickets}
            selectedTicketId={selectedTicketId}
            onSelectTicket={(id) => {
              setSelectedTicketId(id);
              setShowNewTicketForm(false);
            }}
          />
        </aside>

        <section className="detail-view">
          {error && (
            <div className="error-message" style={{ margin: '2rem' }}>
              {error}
            </div>
          )}

          {loading && (
            <div style={{ margin: '2rem', color: '#6e6e80' }}>
              Loading tickets...
            </div>
          )}

          {showNewTicketForm ? (
            <NewTicketForm
              onSubmit={handleCreateTicket}
              onCancel={() => setShowNewTicketForm(false)}
            />
          ) : selectedTicket ? (
            <TicketDetail
              ticket={selectedTicket}
              onProcess={handleProcessTicket}
              onDelete={handleDeleteTicket}
              processing={processing}
            />
          ) : (
            <div className="detail-empty">
              {tickets.length === 0
                ? 'Create your first ticket to get started'
                : 'Select a ticket to view details'}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
