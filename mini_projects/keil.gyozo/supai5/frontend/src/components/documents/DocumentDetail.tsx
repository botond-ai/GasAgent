/**
 * Document detail view component.
 */
import React from 'react';
import type { DocumentDetail as DocumentDetailType } from '../../types';
import '../../styles/components.css';

interface DocumentDetailProps {
  document: DocumentDetailType;
  onDelete: (docId: string) => void;
  loading: boolean;
}

export const DocumentDetail: React.FC<DocumentDetailProps> = ({
  document,
  onDelete,
  loading,
}) => {
  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getFileIcon = (fileType: string): string => {
    switch (fileType.toLowerCase()) {
      case 'pdf':
        return '📄';
      case 'docx':
        return '📝';
      case 'txt':
        return '📃';
      case 'md':
        return '📋';
      default:
        return '📁';
    }
  };

  return (
    <div className="detail-content">
      <div className="detail-header">
        <h2>{getFileIcon(document.file_type)} {document.title}</h2>
        <div className="detail-meta">
          <span>File: {document.filename}</span>
          <span>Category: {document.category}</span>
          <span>Created: {formatDateTime(document.created_at)}</span>
        </div>
      </div>

      {document.description && (
        <div className="detail-section">
          <h3>Description</h3>
          <p>{document.description}</p>
        </div>
      )}

      <div className="detail-section">
        <h3>Document Statistics</h3>
        <div className="triage-panel">
          <div className="triage-item">
            <span className="triage-label">File Type</span>
            <span className="triage-value">{document.file_type.toUpperCase()}</span>
          </div>
          <div className="triage-item">
            <span className="triage-label">Chunks</span>
            <span className="triage-value">{document.chunk_count}</span>
          </div>
          <div className="triage-item">
            <span className="triage-label">Category</span>
            <span className="triage-value">{document.category}</span>
          </div>
        </div>
      </div>

      <div className="detail-section">
        <h3>Document Content ({document.chunks.length} chunks)</h3>
        <div className="document-chunks">
          {document.chunks.map((chunk, idx) => (
            <div key={idx} className="citation-item">
              <div className="citation-meta" style={{ marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>Chunk {chunk.chunk_index + 1}</span>
              </div>
              <div className="citation-text">{chunk.text}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="action-bar">
        <button
          className="btn btn-danger"
          onClick={() => onDelete(document.id)}
          disabled={loading}
        >
          Delete Document
        </button>
      </div>
    </div>
  );
};
