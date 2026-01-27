import React, { useEffect, useRef, useState } from 'react';
import { useActivity, LogEntry } from '../contexts/ActivityContext';
import '../styles/activity-logger.css';

interface DevLog {
  timestamp: number;
  feature: string;
  event: string;
  status: string;
  description: string;
  details?: Record<string, any>;
}

const ActivityLogger: React.FC = () => {
  const { entries, clearActivities, addActivity } = useActivity();
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [apiActivities, setApiActivities] = useState<any[]>([]);
  const [devLogs, setDevLogs] = useState<DevLog[]>([]);
  const [featureFilter, setFeatureFilter] = useState<string | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch activities from backend API
  const fetchActivities = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/activities?count=100');
      if (response.ok) {
        const data = await response.json();
        setApiActivities(data.activities || []);
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    }
  };

  // Fetch development logs from backend API (NEW)
  const fetchDevLogs = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/dev-logs?limit=100');
      if (response.ok) {
        const data = await response.json();
        setDevLogs(data.logs || []);
        console.log('📊 Dev logs fetched:', data.logs?.length || 0, 'logs');
      }
    } catch (error) {
      console.error('Failed to fetch dev logs:', error);
    }
  };

  // Start polling when panel is open
  useEffect(() => {
    if (isOpen) {
      fetchActivities(); // Fetch immediately
      fetchDevLogs(); // Fetch dev logs immediately
      pollingIntervalRef.current = setInterval(() => {
        fetchActivities();
        fetchDevLogs();
      }, 500); // Poll every 500ms for both
    } else {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [isOpen]);

  const formatTime = (timestamp: any): string => {
    try {
      if (!timestamp) return 'Ismeretlen idő';
      
      let date: Date;
      
      // Ha szám, direkten milliszekundumként kezelj
      if (typeof timestamp === 'number') {
        date = new Date(timestamp);
      } 
      // Ha string (ISO format), parseld
      else if (typeof timestamp === 'string') {
        date = new Date(timestamp);
      }
      // Egyéb esetben skip
      else {
        return 'Érvénytelen formátum';
      }
      
      // Ellenőrizd, hogy valid dátum-e
      if (isNaN(date.getTime())) {
        console.error('Invalid timestamp:', timestamp);
        return 'Érvénytelen dátum';
      }
      
      return date.toLocaleTimeString('hu-HU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (e) {
      console.error('Date formatting error:', e, 'timestamp:', timestamp);
      return 'Dátumhiba';
    }
  };

  const getTypeIcon = (type: string): string => {
    switch (type) {
      case 'success':
        return '✓';
      case 'error':
        return '✗';
      case 'warning':
        return '⚠';
      case 'processing':
        return '⏳';
      case 'info':
      default:
        return 'ℹ';
    }
  };

  // Combine local entries, API activities, and dev logs - sorted by timestamp
  const combinedLogs = [
    // Local entries
    ...entries.map(e => ({
      id: e.id,
      type: 'activity',
      timestamp: e.timestamp,
      message: e.message,
      feature: null
    })),
    // API activities
    ...apiActivities.map(a => ({
      id: a.id,
      type: 'activity',
      timestamp: a.timestamp,
      message: a.message,
      feature: null
    })),
    // Dev logs
    ...devLogs.map(log => ({
      id: `${log.feature}-${log.timestamp}`,
      type: 'dev-log',
      timestamp: log.timestamp,
      feature: log.feature,
      event: log.event,
      description: log.description,
      status: log.status,
      details: log.details
    }))
  ].sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime();
    const timeB = new Date(b.timestamp).getTime();
    return timeB - timeA; // Newest first
  });

  // Filter logs by selected feature
  const filteredLogs = featureFilter
    ? combinedLogs.filter(log => {
        if (log.type === 'activity') return featureFilter === 'activities';
        return log.feature === featureFilter;
      })
    : combinedLogs;

  const getFeatureEmoji = (feature: string | null): string => {
    if (!feature) return '📋';
    switch (feature) {
      case 'conversation_history':
        return '#1️⃣';
      case 'retrieval_check':
        return '#2️⃣';
      case 'checkpointing':
        return '#3️⃣';
      case 'reranking':
        return '#4️⃣';
      case 'hybrid_search':
        return '#5️⃣';
      default:
        return '📌';
    }
  };

  return (
    <div className="activity-logger">
      <button
        className="activity-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
        title={isOpen ? 'Bezárás' : 'Megnyitás'}
      >
        📋 Tevékenység ({combinedLogs.length})
      </button>

      {isOpen && (
        <>
          <div className="activity-overlay" onClick={() => setIsOpen(false)}></div>
          <div className={`activity-panel ${isExpanded ? 'expanded' : ''}`}>
            <div className="activity-panel-header">
              <h3>📋 Háttérfolyamatok</h3>
              <div className="activity-panel-controls">
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  title={isExpanded ? 'Kis méret' : 'Teljes méret'}
                  className="expand-btn"
                >
                  {isExpanded ? '🔽' : '🔼'}
                </button>
                <button 
                  onClick={() => {
                    clearActivities();
                    setApiActivities([]);
                    setDevLogs([]);
                  }} 
                  title="Törlés"
                >
                  🗑
                </button>
                <button onClick={() => setIsOpen(false)} title="Bezárás" className="close-btn">
                  ✕
                </button>
              </div>
            </div>

            {/* Feature filter buttons */}
            <div className="feature-filters">
              <button
                className={`filter-btn ${featureFilter === null ? 'active' : ''}`}
                onClick={() => setFeatureFilter(null)}
              >
                Összes ({combinedLogs.length})
              </button>
              <button
                className={`filter-btn ${featureFilter === 'activities' ? 'active' : ''}`}
                onClick={() => setFeatureFilter('activities')}
              >
                📋 Tevékenységek
              </button>
              <button
                className={`filter-btn ${featureFilter === 'conversation_history' ? 'active' : ''}`}
                onClick={() => setFeatureFilter('conversation_history')}
              >
                #1️⃣ Beszélgetés
              </button>
              <button
                className={`filter-btn ${featureFilter === 'retrieval_check' ? 'active' : ''}`}
                onClick={() => setFeatureFilter('retrieval_check')}
              >
                #2️⃣ Keresés
              </button>
              <button
                className={`filter-btn ${featureFilter === 'checkpointing' ? 'active' : ''}`}
                onClick={() => setFeatureFilter('checkpointing')}
              >
                #3️⃣ Mentés
              </button>
              <button
                className={`filter-btn ${featureFilter === 'reranking' ? 'active' : ''}`}
                onClick={() => setFeatureFilter('reranking')}
              >
                #4️⃣ Rangsorolás
              </button>
            </div>

            <div className="activity-panel-content" ref={contentRef}>
              {filteredLogs.length === 0 ? (
                <div className="empty-state">
                  <p>Nincsenek tevékenységek a szűrőhöz...</p>
                </div>
              ) : (
                <ul className="activity-list">
                  {filteredLogs.map((item) => {
                    // Activity log item
                    if (item.type === 'activity') {
                      return (
                        <li key={item.id} className={`activity-item activity-info`}>
                          <div className="activity-icon">📋</div>
                          <div className="activity-content">
                            <div className="activity-message">{item.message}</div>
                            <div className="activity-time">
                              {formatTime(item.timestamp)}
                            </div>
                          </div>
                        </li>
                      );
                    }

                    // Dev log item
                    return (
                      <li key={item.id} className={`dev-log-inline dev-log-${item.status}`}>
                        <div className="dev-log-inline-header">
                          <span className="dev-log-feature-badge">
                            {getFeatureEmoji(item.feature)} {item.feature?.replace(/_/g, ' ').toUpperCase()}
                          </span>
                          <span className="dev-log-event-badge">{item.event}</span>
                          <span className="dev-log-status-icon">
                            {item.status === 'success' ? '✅' : item.status === 'error' ? '❌' : item.status === 'processing' ? '🔄' : 'ℹ️'}
                          </span>
                          <span className="dev-log-time">
                            {new Date(item.timestamp).toLocaleTimeString('hu-HU')}
                          </span>
                        </div>
                        <div className="dev-log-description">{item.description}</div>
                        {item.details && Object.keys(item.details).length > 0 && (
                          <details className="dev-log-details">
                            <summary>Részletek</summary>
                            <pre>{JSON.stringify(item.details, null, 2)}</pre>
                          </details>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="activity-panel-footer">
              Összesen: {combinedLogs.length} esemény
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ActivityLogger;

