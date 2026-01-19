import { useEffect } from 'react';
import { Trash2, Plus, AlertCircle, X } from 'lucide-react';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import { useChatStore } from '../../store/chatStore';

export default function ChatContainer() {
  const {
    messages,
    isLoading,
    error,
    currentSessionId,
    sendMessage,
    clearMessages,
    clearError,
  } = useChatStore();

  // Clear error after 5 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(clearError, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, clearError]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
        <div>
          <h2 className="font-semibold text-gray-900">Chat</h2>
          {currentSessionId && (
            <p className="text-xs text-gray-500">
              Session: {currentSessionId.slice(0, 8)}...
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={clearMessages}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Új beszélgetés</span>
          </button>

          {messages.length > 0 && (
            <button
              onClick={clearMessages}
              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Beszélgetés törlése"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mx-4 mt-4 flex items-center gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-red-800">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="flex-1 text-sm">{error}</p>
          <button
            onClick={clearError}
            className="p-1 hover:bg-red-100 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Messages */}
      <MessageList messages={messages} />

      {/* Input */}
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}
