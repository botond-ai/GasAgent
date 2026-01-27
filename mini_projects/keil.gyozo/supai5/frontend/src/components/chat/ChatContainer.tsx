/**
 * Main chat container component.
 */
import { MessageList } from './MessageList';
import { InputBar } from './InputBar';
import { useChat } from '../../hooks/useChat';
import './chat.css';

interface ChatContainerProps {
  ticketId?: string;
}

export function ChatContainer({ ticketId }: ChatContainerProps) {
  const {
    messages,
    isLoading,
    error,
    sendMessage,
    resetChat,
  } = useChat(ticketId);

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="chat-header-info">
          <h1>SupportAI</h1>
          <span className="chat-subtitle">AI-Powered Support Chat</span>
        </div>
        <button
          className="new-chat-btn"
          onClick={resetChat}
          title="Start new conversation"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          New Chat
        </button>
      </div>

      <div className="chat-main">
        <MessageList messages={messages} isLoading={isLoading} />
      </div>

      <div className="chat-footer">
        {error && (
          <div className="chat-error">
            {error}
          </div>
        )}
        <InputBar
          onSend={sendMessage}
          disabled={isLoading}
          placeholder={isLoading ? 'AI is processing...' : 'Describe your issue...'}
        />
      </div>
    </div>
  );
}
