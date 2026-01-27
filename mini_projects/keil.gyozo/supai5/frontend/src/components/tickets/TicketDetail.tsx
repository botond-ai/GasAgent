/**
 * Ticket detail view component.
 */
import React from 'react';
import type { Ticket } from '../../types';
import '../../styles/components.css';

interface TicketDetailProps {
  ticket: Ticket;
  onProcess: (ticketId: string) => void;
  onDelete: (ticketId: string) => void;
  processing: boolean;
}

export const TicketDetail: React.FC<TicketDetailProps> = ({
  ticket,
  onProcess,
  onDelete,
  processing,
}) => {
  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const canProcess = ticket.status === 'new' || ticket.status === 'error';

  return (
    <div className="detail-content">
      <div className="detail-header">
        <h2>{ticket.subject}</h2>
        <div className="detail-meta">
          <span>From: {ticket.customer_name}</span>
          <span>Email: {ticket.customer_email}</span>
          <span>Created: {formatDateTime(ticket.created_at)}</span>
        </div>
      </div>

      <div className="detail-section">
        <h3>Customer Message</h3>
        <p>{ticket.message}</p>
      </div>

      {ticket.triage_result && (
        <>
          <div className="detail-section">
            <h3>Triage Analysis</h3>
            <div className="triage-panel">
              <div className="triage-item">
                <span className="triage-label">Category</span>
                <span className="triage-value">{ticket.triage_result.triage.category}</span>
              </div>
              <div className="triage-item">
                <span className="triage-label">Priority</span>
                <span className={`triage-value priority-${ticket.triage_result.triage.priority.toLowerCase()}`}>
                  {ticket.triage_result.triage.priority}
                </span>
              </div>
              <div className="triage-item">
                <span className="triage-label">SLA</span>
                <span className="triage-value">{ticket.triage_result.triage.sla_hours}h</span>
              </div>
              <div className="triage-item">
                <span className="triage-label">Team</span>
                <span className="triage-value">{ticket.triage_result.triage.suggested_team}</span>
              </div>
              <div className="triage-item">
                <span className="triage-label">Sentiment</span>
                <span className={`triage-value sentiment-${ticket.triage_result.triage.sentiment}`}>
                  {ticket.triage_result.triage.sentiment}
                </span>
              </div>
              <div className="triage-item">
                <span className="triage-label">Confidence</span>
                <span className="triage-value">
                  {(ticket.triage_result.triage.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h3>AI-Generated Response</h3>
            <div className="answer-draft">
              <div className="answer-section">
                <div className="answer-section-label">Greeting</div>
                <div className="answer-text">{ticket.triage_result.answer_draft.greeting}</div>
              </div>
              <div className="answer-section">
                <div className="answer-section-label">Body</div>
                <div className="answer-text">{ticket.triage_result.answer_draft.body}</div>
              </div>
              <div className="answer-section">
                <div className="answer-section-label">Closing</div>
                <div className="answer-text">{ticket.triage_result.answer_draft.closing}</div>
              </div>
            </div>
          </div>

          {ticket.triage_result.citations.length > 0 && (
            <div className="detail-section">
              <h3>Knowledge Base Citations</h3>
              <div className="citations">
                {ticket.triage_result.citations.map((citation, idx) => (
                  <div key={idx} className="citation-item">
                    <div className="citation-text">{citation.text}</div>
                    <div className="citation-meta">
                      <span>{citation.source}</span>
                      <span>Relevance: {(citation.relevance * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="detail-section">
            <h3>Policy Compliance</h3>
            <div className="triage-panel">
              <div className="triage-item">
                <span className="triage-label">Refund Promise</span>
                <span className="triage-value">
                  {ticket.triage_result.policy_check.refund_promise ? 'Yes ⚠️' : 'No ✓'}
                </span>
              </div>
              <div className="triage-item">
                <span className="triage-label">SLA Mentioned</span>
                <span className="triage-value">
                  {ticket.triage_result.policy_check.sla_mentioned ? 'Yes ⚠️' : 'No ✓'}
                </span>
              </div>
              <div className="triage-item">
                <span className="triage-label">Escalation Needed</span>
                <span className="triage-value">
                  {ticket.triage_result.policy_check.escalation_needed ? 'Yes ⚠️' : 'No ✓'}
                </span>
              </div>
              <div className="triage-item">
                <span className="triage-label">Compliance</span>
                <span className="triage-value">
                  {ticket.triage_result.policy_check.compliance.toUpperCase()}
                </span>
              </div>
            </div>
          </div>
        </>
      )}

      <div className="action-bar">
        {canProcess && (
          <button
            className="btn btn-primary"
            onClick={() => onProcess(ticket.id)}
            disabled={processing}
          >
            {processing ? (
              <>
                <span className="spinner"></span>
                Processing...
              </>
            ) : (
              'Process with AI'
            )}
          </button>
        )}
        <button
          className="btn btn-danger"
          onClick={() => onDelete(ticket.id)}
          disabled={processing}
        >
          Delete
        </button>
      </div>
    </div>
  );
};
