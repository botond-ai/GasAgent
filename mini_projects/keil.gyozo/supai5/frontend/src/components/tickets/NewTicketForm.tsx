/**
 * New ticket creation form component.
 */
import React, { useState } from 'react';
import type { TicketCreate } from '../../types';
import '../../styles/components.css';

interface NewTicketFormProps {
  onSubmit: (data: TicketCreate) => Promise<void>;
  onCancel: () => void;
}

export const NewTicketForm: React.FC<NewTicketFormProps> = ({ onSubmit, onCancel }) => {
  const [formData, setFormData] = useState<TicketCreate>({
    customer_name: '',
    customer_email: '',
    subject: '',
    message: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit(formData);
      // Reset form
      setFormData({
        customer_name: '',
        customer_email: '',
        subject: '',
        message: '',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const isValid =
    formData.customer_name.trim() !== '' &&
    formData.customer_email.trim() !== '' &&
    formData.subject.trim() !== '' &&
    formData.message.trim() !== '';

  return (
    <div className="detail-content">
      <div className="detail-header">
        <h2>Create New Ticket</h2>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="customer_name">
            Customer Name
          </label>
          <input
            type="text"
            id="customer_name"
            name="customer_name"
            className="form-input"
            value={formData.customer_name}
            onChange={handleChange}
            required
            placeholder="John Doe"
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="customer_email">
            Customer Email
          </label>
          <input
            type="email"
            id="customer_email"
            name="customer_email"
            className="form-input"
            value={formData.customer_email}
            onChange={handleChange}
            required
            placeholder="john.doe@example.com"
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="subject">
            Subject
          </label>
          <input
            type="text"
            id="subject"
            name="subject"
            className="form-input"
            value={formData.subject}
            onChange={handleChange}
            required
            placeholder="Issue with product delivery"
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="message">
            Message
          </label>
          <textarea
            id="message"
            name="message"
            className="form-textarea"
            value={formData.message}
            onChange={handleChange}
            required
            placeholder="Describe the issue..."
          />
        </div>

        <div className="action-bar">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!isValid || submitting}
          >
            {submitting ? (
              <>
                <span className="spinner"></span>
                Creating...
              </>
            ) : (
              'Create Ticket'
            )}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};
