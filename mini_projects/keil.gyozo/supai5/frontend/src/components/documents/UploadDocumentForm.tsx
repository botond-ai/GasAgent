/**
 * Upload document form component.
 */
import React, { useState } from 'react';
import '../../styles/components.css';

const CATEGORIES = [
  'Billing',
  'Technical',
  'Account',
  'Shipping',
  'Product',
  'General'
];

interface UploadDocumentFormProps {
  onSubmit: (file: File, title: string, category: string, description?: string) => Promise<void>;
  onCancel: () => void;
}

export const UploadDocumentForm: React.FC<UploadDocumentFormProps> = ({
  onSubmit,
  onCancel,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('Technical');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];

      // Validate file extension
      const allowedExtensions = ['.pdf', '.txt', '.docx', '.md'];
      const fileExtension = '.' + selectedFile.name.split('.').pop()?.toLowerCase();

      if (!allowedExtensions.includes(fileExtension)) {
        setError(`Unsupported file type. Allowed: PDF, TXT, DOCX, MD`);
        return;
      }

      // Validate file size (10MB max)
      const maxSize = 10 * 1024 * 1024;
      if (selectedFile.size > maxSize) {
        setError('File too large. Maximum size: 10MB');
        return;
      }

      setFile(selectedFile);
      setError(null);

      // Auto-fill title from filename if empty
      if (!title) {
        const fileName = selectedFile.name.replace(/\.[^/.]+$/, '');
        setTitle(fileName);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file || !title.trim()) {
      setError('Please select a file and enter a title');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await onSubmit(file, title.trim(), category, description.trim() || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setSubmitting(false);
    }
  };

  const isValid = file !== null && title.trim() !== '';

  return (
    <div className="detail-content">
      <div className="detail-header">
        <h2>Upload New Document</h2>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="file">
            File
          </label>
          <input
            type="file"
            id="file"
            className="form-input"
            onChange={handleFileChange}
            accept=".pdf,.txt,.docx,.md"
            disabled={submitting}
          />
          <small style={{ color: '#6e6e80', marginTop: '0.25rem', display: 'block' }}>
            Supported: PDF, TXT, DOCX, MD (max 10MB)
          </small>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="title">
            Title
          </label>
          <input
            type="text"
            id="title"
            className="form-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            placeholder="e.g., Billing FAQ"
            disabled={submitting}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="category">
            Category
          </label>
          <select
            id="category"
            className="form-input"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={submitting}
          >
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="description">
            Description (optional)
          </label>
          <textarea
            id="description"
            className="form-textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description of the document..."
            disabled={submitting}
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
                Uploading...
              </>
            ) : (
              'Upload & Index'
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
