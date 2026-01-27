/**
 * Document list sidebar component.
 */
import React from 'react';
import type { Document } from '../../types';
import '../../styles/components.css';

interface DocumentListProps {
  documents: Document[];
  selectedDocumentId: string | null;
  onSelectDocument: (docId: string) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  selectedDocumentId,
  onSelectDocument,
}) => {
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
    <div className="ticket-list">
      {documents.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#8e8ea0' }}>
          No documents found
        </div>
      ) : (
        documents.map((doc) => (
          <div
            key={doc.id}
            className={`ticket-item ${selectedDocumentId === doc.id ? 'active' : ''}`}
            onClick={() => onSelectDocument(doc.id)}
          >
            <div className="ticket-header">
              <h3 className="ticket-subject">
                {getFileIcon(doc.file_type)} {doc.title}
              </h3>
              <span className={`ticket-status status-${doc.category.toLowerCase()}`}>
                {doc.category}
              </span>
            </div>
            <p className="ticket-customer">
              {doc.filename} • {formatDate(doc.created_at)}
            </p>
            <p className="ticket-message-preview">
              {doc.chunk_count} chunks indexed
              {doc.description && ` • ${doc.description}`}
            </p>
          </div>
        ))
      )}
    </div>
  );
};
