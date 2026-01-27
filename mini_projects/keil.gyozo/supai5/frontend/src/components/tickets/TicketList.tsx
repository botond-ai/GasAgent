/**
 * Ticket list sidebar component.
 */
import React from 'react';
import type { Ticket } from '../../types';
import '../../styles/components.css';

interface TicketListProps {
  tickets: Ticket[];
  selectedTicketId: string | null;
  onSelectTicket: (ticketId: string) => void;
}

export const TicketList: React.FC<TicketListProps> = ({
  tickets,
  selectedTicketId,
  onSelectTicket,
}) => {
  const getStatusClass = (status: Ticket['status']): string => {
    return `ticket-status status-${status}`;
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div className="ticket-list">
      {tickets.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#8e8ea0' }}>
          No tickets found
        </div>
      ) : (
        tickets.map((ticket) => (
          <div
            key={ticket.id}
            className={`ticket-item ${selectedTicketId === ticket.id ? 'active' : ''}`}
            onClick={() => onSelectTicket(ticket.id)}
          >
            <div className="ticket-header">
              <h3 className="ticket-subject">{ticket.subject}</h3>
              <span className={getStatusClass(ticket.status)}>
                {ticket.status}
              </span>
            </div>
            <p className="ticket-customer">
              {ticket.customer_name} • {formatDate(ticket.created_at)}
            </p>
            <p className="ticket-message-preview">{ticket.message}</p>
          </div>
        ))
      )}
    </div>
  );
};
