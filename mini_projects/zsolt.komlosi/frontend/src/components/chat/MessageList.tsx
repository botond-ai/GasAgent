import { useRef, useEffect } from 'react';
import { User, Bot } from 'lucide-react';
import type { Message } from '../../types';
import CitationCard from './CitationCard';
import TriageBadge from './TriageBadge';
import TypingIndicator from './TypingIndicator';

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-primary-100 rounded-full flex items-center justify-center">
            <Bot className="w-8 h-8 text-primary-600" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Üdvözlöm a SupportAI-ban!
          </h3>
          <p className="text-gray-500 max-w-md">
            Írja le a problémáját vagy kérdését, és segítek megtalálni a választ
            a tudásbázisunkból.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex gap-3 ${
            message.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          {message.role === 'assistant' && (
            <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
              <Bot className="w-5 h-5 text-primary-600" />
            </div>
          )}

          <div
            className={`max-w-[70%] ${
              message.role === 'user'
                ? 'bg-primary-600 text-white rounded-2xl rounded-br-md'
                : 'bg-white border border-gray-200 rounded-2xl rounded-bl-md'
            } px-4 py-3 shadow-sm`}
          >
            {message.isLoading ? (
              <TypingIndicator />
            ) : (
              <>
                {message.triage && (
                  <div className="mb-2">
                    <TriageBadge triage={message.triage} />
                  </div>
                )}

                <div
                  className={`whitespace-pre-wrap ${
                    message.role === 'user' ? 'text-white' : 'text-gray-800'
                  }`}
                >
                  {message.content}
                </div>

                {message.citations && message.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-xs text-gray-500 mb-2">
                      Felhasznált források:
                    </p>
                    <div className="space-y-2">
                      {message.citations.map((citation) => (
                        <CitationCard key={citation.id} citation={citation} />
                      ))}
                    </div>
                  </div>
                )}

                <div
                  className={`text-xs mt-2 ${
                    message.role === 'user' ? 'text-primary-200' : 'text-gray-400'
                  }`}
                >
                  {new Date(message.timestamp).toLocaleTimeString('hu-HU', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
              </>
            )}
          </div>

          {message.role === 'user' && (
            <div className="flex-shrink-0 w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
              <User className="w-5 h-5 text-gray-600" />
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
