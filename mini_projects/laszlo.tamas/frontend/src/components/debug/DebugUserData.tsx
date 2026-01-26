import React from 'react';
import { DebugInfo } from '../../types';

interface DebugUserDataProps {
  debugInfo: DebugInfo;
  isOpen: boolean;
  onToggle: () => void;
  formatTimestamp: (timestamp: string) => string;
}

/**
 * User Data Accordion Section (SOLID: Single Responsibility)
 * Displays user metadata, tenant info, and message counts
 */
export const DebugUserData: React.FC<DebugUserDataProps> = ({ 
  debugInfo, 
  isOpen, 
  onToggle, 
  formatTimestamp 
}) => {
  return (
    <section className="debug-section">
      <div 
        className="debug-accordion-header"
        onClick={onToggle}
        style={{ cursor: 'pointer', userSelect: 'none' }}
      >
        <h3>
          {isOpen ? '▼' : '▶'} 📊 User Data (Database)
        </h3>
      </div>
      {isOpen && (
        <div className="debug-data-grid" style={{ marginTop: '10px' }}>
          <div><strong>User ID:</strong> {debugInfo.user_data.user_id}</div>
          <div><strong>Name:</strong> {debugInfo.user_data.firstname} {debugInfo.user_data.lastname}</div>
          <div><strong>Nickname:</strong> {debugInfo.user_data.nickname}</div>
          <div><strong>Email:</strong> {debugInfo.user_data.email}</div>
          <div><strong>Role:</strong> {debugInfo.user_data.role}</div>
          <div><strong>Language:</strong> {debugInfo.user_data.default_lang || 'N/A'}</div>
          <div><strong>Active:</strong> {debugInfo.user_data.is_active ? "Yes" : "No"}</div>
          <div><strong>Created:</strong> {formatTimestamp(debugInfo.user_data.created_at)}</div>
        </div>
      )}
    </section>
  );
};
