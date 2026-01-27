/**
 * Individual chat message bubble component.
 */
import type { Message } from '../../types/chat';
import './chat.css';

interface MessageBubbleProps {
  message: Message;
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getPriorityColor(priority: string): string {
  switch (priority) {
    case 'P1': return '#dc3545';
    case 'P2': return '#fd7e14';
    case 'P3': return '#28a745';
    default: return '#6c757d';
  }
}

function getSentimentEmoji(sentiment: string): string {
  switch (sentiment) {
    case 'frustrated': return '😤';
    case 'satisfied': return '😊';
    default: return '😐';
  }
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div className={`message-bubble-wrapper ${isUser ? 'user' : 'assistant'} ${isSystem ? 'system' : ''}`}>
      <div className={`message-bubble ${isUser ? 'user' : 'assistant'} ${isSystem ? 'system' : ''}`}>
        <div className="message-content">
          {message.content.split('\n').map((line, i) => (
            <p key={i}>{line || '\u00A0'}</p>
          ))}
        </div>

        {message.metadata && (
          <div className="message-metadata">
            {message.metadata.category && (
              <span className="metadata-tag category">
                {message.metadata.category}
              </span>
            )}
            {message.metadata.priority && (
              <span
                className="metadata-tag priority"
                style={{ backgroundColor: getPriorityColor(message.metadata.priority) }}
              >
                {message.metadata.priority}
              </span>
            )}
            {message.metadata.sentiment && (
              <span className="metadata-tag sentiment">
                {getSentimentEmoji(message.metadata.sentiment)} {message.metadata.sentiment}
              </span>
            )}
            {message.metadata.suggestedTeam && (
              <span className="metadata-tag team">
                → {message.metadata.suggestedTeam}
              </span>
            )}
          </div>
        )}

        <div className="message-timestamp">
          {formatTimestamp(message.timestamp)}
        </div>
      </div>
    </div>
  );
}
