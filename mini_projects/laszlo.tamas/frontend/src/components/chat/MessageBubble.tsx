import { Message } from "../../types";

interface MessageBubbleProps {
  message: Message;
  onWorkflowClick?: (executionId: string) => void; // NEW: Callback for workflow visualization
}

// Convert text with Excel links to clickable elements
const renderContentWithLinks = (content: string): React.ReactNode => {
  // Pattern to find .xlsx filenames (with or without emoji prefix)
  const xlsxPattern = /([📄📁]\s*)?([a-zA-Z0-9_\-]+\.xlsx)/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;
  let keyIdx = 0;

  while ((match = xlsxPattern.exec(content)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push(content.substring(lastIndex, match.index));
    }
    
    // Add clickable link for the xlsx file
    const filename = match[2];
    const downloadUrl = `/api/excel/${filename}`;
    parts.push(
      <a
        key={keyIdx++}
        href={downloadUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="excel-download-link"
        onClick={(e) => e.stopPropagation()}
      >
        📥 {filename}
      </a>
    );
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < content.length) {
    parts.push(content.substring(lastIndex));
  }
  
  return parts.length > 0 ? parts : content;
};

export const MessageBubble = ({ message, onWorkflowClick }: MessageBubbleProps) => {
  const isUser = message.role === "user";
  const hasWorkflow = !isUser && message.metadata?.execution_id;
  
  const formatResponseTime = (ms: number) => {
    if (ms < 1000) {
      return `${ms}ms`;
    }
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const handleWorkflowClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasWorkflow && onWorkflowClick) {
      onWorkflowClick(message.metadata!.execution_id!);
    }
  };
  
  // Render content - for assistant messages, make xlsx links clickable
  const renderedContent = !isUser 
    ? renderContentWithLinks(message.content)
    : message.content;
  
  return (
    <div 
      className={`message-bubble ${isUser ? "user-message" : "assistant-message"}`}
    >
      <div className="message-role">
        {message.role}
        {hasWorkflow && (
          <span 
            className="workflow-indicator clickable" 
            title="Click to visualize workflow"
            onClick={handleWorkflowClick}
            style={{ cursor: 'pointer' }}
          >
            📊
          </span>
        )}
      </div>
      <div className="message-content">{renderedContent}</div>
      {message.sources && message.sources.length > 0 && (
        <div className="message-sources">
          📚 Források: {message.sources.map((source, idx) => (
            <span key={idx} className="source-badge" title={`Document ID: ${source.id}`}>
              {source.title}
            </span>
          ))}
          {message.ragParams && (
            <span className="rag-params" style={{ marginLeft: '10px', fontSize: '0.85em', color: '#666' }}>
              (TOP_K={message.ragParams.top_k}, MIN_SCORE={message.ragParams.min_score_threshold})
            </span>
          )}
        </div>
      )}
      <div className="message-timestamp">
        {new Date(message.timestamp).toLocaleTimeString()}
        {message.responseTime && (
          <span className="response-timer"> • {formatResponseTime(message.responseTime)}</span>
        )}
      </div>
    </div>
  );
};
