/**
 * ChatContainer Component - Complete Example Implementation
 * 
 * This is the main chat interface component.
 * Copy this as a starting point and customize as needed.
 */

import React, { useRef, useEffect } from 'react';
import { useChat } from '../../hooks/useChat';
import type { Message } from '../../types/chat';
import './ChatContainer.css';

interface ChatContainerProps {
  ticketId?: string;
  showDebug?: boolean;
}

export function ChatContainer({ ticketId, showDebug = false }: ChatContainerProps) {
  const { messages, isLoading, error, createTicket, clearError } = useChat(ticketId);
  const [inputValue, setInputValue] = React.useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const trimmedValue = inputValue.trim();
    if (!trimmedValue || isLoading) return;

    // Clear input immediately for better UX
    setInputValue('');

    // Send message
    await createTicket(trimmedValue);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-main">
        {/* Header */}
        <div className="chat-header">
          <h1>SupportAI Assistant</h1>
          <p>Ask me anything about your order or account</p>
        </div>

        {/* Messages Area */}
        <div className="messages-container">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {/* Typing Indicator */}
          {isLoading && (
            <div className="typing-indicator">
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} />
        </div>

        {/* Error Message */}
        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={clearError}>×</button>
          </div>
        )}

        {/* Input Bar */}
        <div className="input-bar">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            className="send-button"
          >
            {isLoading ? '⏳' : '📤'}
          </button>
        </div>
      </div>

      {/* Debug Panel (if enabled) */}
      {showDebug && <DebugPanel />}
    </div>
  );
}

/**
 * MessageBubble - Individual message component
 */
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div className={`message-wrapper ${isUser ? 'user' : isSystem ? 'system' : 'assistant'}`}>
      <div className="message-bubble">
        {/* Message Content */}
        <div className="message-content">{message.content}</div>

        {/* Metadata (for AI messages) */}
        {message.metadata && (
          <div className="message-metadata">
            <span className="metadata-badge category">
              {message.metadata.category}
            </span>
            <span className={`metadata-badge priority priority-${message.metadata.priority}`}>
              {message.metadata.priority}
            </span>
            <span className={`metadata-badge sentiment sentiment-${message.metadata.sentiment}`}>
              {message.metadata.sentiment}
            </span>
          </div>
        )}

        {/* Timestamp */}
        <div className="message-timestamp">
          {formatTimestamp(message.timestamp)}
        </div>
      </div>
    </div>
  );
}

/**
 * TypingIndicator - Shows when AI is thinking
 */
function TypingIndicator() {
  return (
    <div className="message-wrapper assistant">
      <div className="message-bubble typing">
        <div className="typing-indicator">
          <div className="typing-dot"></div>
          <div className="typing-dot"></div>
          <div className="typing-dot"></div>
        </div>
      </div>
    </div>
  );
}

/**
 * DebugPanel - Optional debug sidebar
 */
function DebugPanel() {
  const [activeTab, setActiveTab] = React.useState<'tools' | 'memory' | 'logs'>('tools');

  return (
    <div className="debug-panel">
      <div className="debug-header">
        <h3>Debug Panel</h3>
      </div>

      <div className="debug-tabs">
        <button
          className={activeTab === 'tools' ? 'active' : ''}
          onClick={() => setActiveTab('tools')}
        >
          Tools
        </button>
        <button
          className={activeTab === 'memory' ? 'active' : ''}
          onClick={() => setActiveTab('memory')}
        >
          Memory
        </button>
        <button
          className={activeTab === 'logs' ? 'active' : ''}
          onClick={() => setActiveTab('logs')}
        >
          Logs
        </button>
      </div>

      <div className="debug-content">
        {activeTab === 'tools' && <ToolCallsView />}
        {activeTab === 'memory' && <MemoryView />}
        {activeTab === 'logs' && <LogsView />}
      </div>
    </div>
  );
}

function ToolCallsView() {
  return <div className="debug-section">Tool calls will appear here...</div>;
}

function MemoryView() {
  return <div className="debug-section">Memory snapshot will appear here...</div>;
}

function LogsView() {
  return <div className="debug-section">Logs will appear here...</div>;
}

/**
 * Format timestamp for display
 */
function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  // For older messages, show time
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}
