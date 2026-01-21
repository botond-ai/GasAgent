import React from 'react';

interface DebugResetActionsProps {
  isOpen: boolean;
  onToggle: () => void;
  isDeleting: boolean;
  isResettingPostgres: boolean;
  isResettingQdrant: boolean;
  isResettingCache: boolean;
  onDeleteHistory: () => Promise<void>;
  onResetPostgres: () => Promise<void>;
  onResetQdrant: () => Promise<void>;
  onResetCache: () => Promise<void>;
}

/**
 * Reset Actions Accordion Section (SOLID: Single Responsibility)
 * Dangerous operations: delete conversations, reset databases, clear caches
 */
export const DebugResetActions: React.FC<DebugResetActionsProps> = ({
  isOpen,
  onToggle,
  isDeleting,
  isResettingPostgres,
  isResettingQdrant,
  isResettingCache,
  onDeleteHistory,
  onResetPostgres,
  onResetQdrant,
  onResetCache
}) => {
  return (
    <section className="debug-section">
      <div 
        className="debug-accordion-header"
        onClick={onToggle}
        style={{ cursor: 'pointer', userSelect: 'none' }}
      >
        <h3>
          {isOpen ? '▼' : '▶'} 🗑️ Reset Actions (Dangerous)
        </h3>
      </div>
      {isOpen && (
        <div className="debug-action-buttons" style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <button
            className="reset-button reset-history"
            onClick={onDeleteHistory}
            disabled={isDeleting}
            title="Delete all chat history for this user"
          >
            🗑️ {isDeleting ? "Deleting..." : "Delete Chat History"}
          </button>
          <button
            className="reset-button reset-postgres"
            onClick={onResetPostgres}
            disabled={isResettingPostgres}
            title="Delete all documents and chunks from PostgreSQL"
          >
            🗑️ {isResettingPostgres ? "Deleting..." : "Delete Docs from Postgres"}
          </button>
          <button
            className="reset-button reset-qdrant"
            onClick={onResetQdrant}
            disabled={isResettingQdrant}
            title="Delete all document vectors from Qdrant"
          >
            🗑️ {isResettingQdrant ? "Deleting..." : "Delete Docs from Qdrant"}
          </button>
          <button
            className="reset-button reset-cache"
            onClick={onResetCache}
            disabled={isResettingCache}
            title="Clear all caches (database + memory)"
            style={{ backgroundColor: '#059669' }}
          >
            🗑️ {isResettingCache ? "Clearing..." : "Clear All Caches"}
          </button>
        </div>
      )}
    </section>
  );
};
