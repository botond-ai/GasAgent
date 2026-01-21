/**
 * DocumentShareModal Component
 * Shows document sharing status (visibility)
 * 
 * Note: Knowledge Router currently uses simple visibility model (private/tenant).
 * Fine-grained permission system (like KA Chat) is planned for future phase.
 */

import { DocumentSummary } from '../../types';
import './DocumentShareModal.css';

interface DocumentShareModalProps {
  document: DocumentSummary;
  onClose: () => void;
}

export function DocumentShareModal({ document, onClose }: DocumentShareModalProps) {
  const isPrivate = document.visibility === 'private';
  const isTenantWide = document.visibility === 'tenant';

  return (
    <div className="share-modal-overlay" onClick={onClose}>
      <div className="share-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="share-modal-header">
          <h2>📤 Document Sharing</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="document-info-box">
          <h3>{document.title}</h3>
          <p className="document-source">{document.source}</p>
        </div>

        <div className="visibility-status">
          <h4>Current Visibility</h4>
          {isPrivate && (
            <div className="visibility-card private">
              <div className="visibility-icon">🔒</div>
              <div className="visibility-details">
                <strong>Private</strong>
                <p>Only you can access this document</p>
              </div>
            </div>
          )}
          {isTenantWide && (
            <div className="visibility-card tenant-wide">
              <div className="visibility-icon">🏢</div>
              <div className="visibility-details">
                <strong>Tenant-wide</strong>
                <p>All users in your organization can access this document</p>
              </div>
            </div>
          )}
        </div>

        <div className="info-box">
          <p><strong>ℹ️ Sharing Model:</strong></p>
          <p>
            Knowledge Router uses a simple visibility model:
          </p>
          <ul>
            <li><strong>Private:</strong> Only the owner can see and use the document</li>
            <li><strong>Tenant-wide:</strong> All users in the organization can see and use the document</li>
          </ul>
          <p className="future-note">
            📝 <em>Fine-grained permission system (read, write, admin) is planned for a future release.</em>
          </p>
        </div>

        <div className="share-modal-footer">
          <button onClick={onClose} className="close-footer-button">Close</button>
        </div>
      </div>
    </div>
  );
}
