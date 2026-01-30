/**
 * MessageBubble component - Displays individual chat messages.
 */
import React from 'react';
import { ChatMessage } from '../types';
import { formatTime } from '../utils';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';

  const openExcelPopup = async (filename: string) => {
    console.log(`Attempting to open Excel popup for: ${filename}`);
    
    try {
      // Basic check for xlsx library
      const XLSX = (window as any).XLSX;
      if (!XLSX) {
        console.error('XLSX library not found on window object');
        alert('Error: Excel viewer library not loaded. Please refresh the page.');
        return;
      }

      const modal = document.createElement('div');
      modal.style.position = 'fixed';
      modal.style.top = '0';
      modal.style.left = '0';
      modal.style.width = '100%';
      modal.style.height = '100%';
      modal.style.backgroundColor = 'rgba(0,0,0,0.8)';
      modal.style.zIndex = '2000';
      modal.style.display = 'flex';
      modal.style.alignItems = 'center';
      modal.style.justifyContent = 'center';

      const content = document.createElement('div');
      content.style.backgroundColor = '#343541';
      content.style.padding = '20px';
      content.style.borderRadius = '10px';
      content.style.maxWidth = '92%';
      content.style.maxHeight = '92%';
      content.style.overflow = 'hidden';

      const closeModal = () => modal.remove();

      content.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;position:sticky;top:0;background:#444654;padding-bottom:10px;border-bottom:2px solid #565869;z-index:10;">
          <div style="font-weight:800;color:#ececf1;">📄 ${filename}</div>
          <button id="excel-close" style="background:#ef4444;color:white;border:none;padding:10px 14px;border-radius:8px;cursor:pointer;font-weight:700;">✕ Close</button>
        </div>
        <div id="excel-body" style="padding:10px 0; color:#ececf1;">Loading…</div>
      `;

      modal.appendChild(content);
      document.body.appendChild(modal);

      const closeBtn = content.querySelector('#excel-close') as HTMLButtonElement | null;
      if (closeBtn) closeBtn.onclick = closeModal;
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
      });

      const bodyEl = content.querySelector('#excel-body') as HTMLDivElement | null;
      
      console.log(`Fetching document: /documents/${filename}`);
      const res = await fetch(`/documents/${encodeURIComponent(filename)}`);
      console.log(`Fetch response status: ${res.status}`);
      
      if (!res.ok) {
        throw new Error(`Failed to fetch ${filename} (HTTP ${res.status}). Ensure the file exists in 'Issue_types_and_details' folder.`);
      }
      
      const arrayBuffer = await res.arrayBuffer();
      console.log(`File fetched, size: ${arrayBuffer.byteLength} bytes`);
      
      const wb = XLSX.read(arrayBuffer, { type: 'array' });
      const sheetName = wb.SheetNames[0];
      const ws = wb.Sheets[sheetName];

      const rows: any[][] = XLSX.utils.sheet_to_json(ws, { header: 1, blankrows: false });
      if (!rows || rows.length === 0) {
        throw new Error('Excel sheet is empty.');
      }

      console.log(`Parsed ${rows.length} rows`);

      const headerRow = rows[0].map((h) => String(h ?? ''));
      const dataRows = rows.slice(1); // all records

      const escapeHtml = (v: any) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

      let table = '<table style="width:100%;border-collapse:collapse;font-size:14px;">';
      table += '<thead><tr>';
      headerRow.forEach((h) => {
        table += `<th style="position:sticky;top:0;border:2px solid #565869;padding:10px 8px;background:#444654;color:#ececf1;text-align:left;font-weight:800;">${escapeHtml(h)}</th>`;
      });
      table += '</tr></thead><tbody>';
      dataRows.forEach((r, idx) => {
        const bg = idx % 2 === 0 ? '#40414f' : '#2a2b32';
        table += `<tr style="background:${bg};color:#ececf1;">`;
        for (let i = 0; i < headerRow.length; i++) {
          table += `<td style="border:1px solid #565869;padding:10px 8px;color:#ececf1;">${escapeHtml(r[i])}</td>`;
        }
        table += '</tr>';
      });
      table += '</tbody></table>';

      if (bodyEl) {
        bodyEl.innerHTML = `
          <div style="margin-bottom:8px;color:#acacbe;font-size:12px;">Sheet: <b style="color:#ececf1;">${escapeHtml(sheetName)}</b> • Showing <b style="color:#ececf1;">${dataRows.length}</b> records</div>
          <div style="height:600px;overflow-y:auto;overflow-x:auto;border:2px solid #565869;border-radius:10px;background:#40414f;">
            ${table}
          </div>
        `;
      }
    } catch (err) {
      console.error('Error opening Excel popup:', err);
      const msg = err instanceof Error ? err.message : String(err);
      
      // Use alert for immediate feedback if modal isn't open yet, or update modal body
      const existingModal = document.querySelector('div[style*="z-index: 2000"]');
      if (existingModal) {
        const bodyEl = existingModal.querySelector('#excel-body');
        if (bodyEl) {
           bodyEl.innerHTML = `<div style="color:#ef4444;font-weight:700;">Error loading document</div><div style="margin-top:6px;color:#acacbe;">${msg}</div>`;
        }
      } else {
        alert(`Failed to open document: ${msg}`);
      }
    }
  };
  
  // Parse markdown links in content
  const parseMarkdownLinks = (text: string) => {
    const linkRegex = /\[([^\]]+)\]\(javascript:openDocument\('([^']+)'\)\)/g;
    const parts: (string | React.ReactElement)[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    
    while ((match = linkRegex.exec(text)) !== null) {
      // Add text before the link
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      
      const linkText = match[1];
      const filename = match[2];
      
      // Add the link as a clickable element
      parts.push(
        <a 
          key={`link-${match.index}`}
          href="#" 
          onClick={(e: React.MouseEvent) => {
            console.log('Link clicked!', linkText, filename);
            e.preventDefault();
            e.stopPropagation();
            openExcelPopup(filename);
          }}
          style={{ color: '#007bff', textDecoration: 'underline', cursor: 'pointer', fontWeight: 'bold' }}
        >
          {linkText}
        </a>
      );
      
      lastIndex = linkRegex.lastIndex;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }
    
    return parts.length > 0 ? parts : text;
  };
  
  return (
    <div className={`message-container ${isUser ? 'user' : 'assistant'}`}>
      <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
        <div className="message-content">
          {isUser ? message.content : parseMarkdownLinks(message.content)}
        </div>
        <div className="message-time">{formatTime(message.timestamp)}</div>
        
        {message.toolsUsed && message.toolsUsed.length > 0 && (
          <div className="tools-used">
            <div className="tools-label">🛠️ Tools used:</div>
            {message.toolsUsed.map((tool, idx) => (
              <div key={idx} className="tool-item-wrapper">
                {tool.name === 'json_creator' ? (
                  <details className="json-dropdown">
                    <summary className="tool-item" style={{ cursor: 'pointer', listStyle: 'none' }}>
                      <span className={`tool-status ${tool.success ? 'success' : 'error'}`}>
                        {tool.success ? '✓' : '✗'}
                      </span>
                      <span className="tool-name">📋 {tool.name}</span>
                      {tool.system_message && (
                        <span className="tool-details"> - {tool.system_message}</span>
                      )}
                      <span style={{ marginLeft: '8px', color: '#acacbe' }}>▼</span>
                    </summary>
                    <div className="json-content" style={{
                      marginTop: '8px',
                      padding: '12px',
                      backgroundColor: '#2a2b32',
                      borderRadius: '8px',
                      border: '1px solid #565869',
                      maxHeight: '400px',
                      overflowY: 'auto'
                    }}>
                      <pre style={{
                        margin: 0,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        fontSize: '12px',
                        color: '#ececf1',
                        fontFamily: 'monospace'
                      }}>
                        {tool.arguments?.ticket_data 
                          ? JSON.stringify(tool.arguments.ticket_data, null, 2)
                          : (tool.detailed_message || tool.system_message || 'No JSON data available')}
                      </pre>
                    </div>
                  </details>
                ) : (
                  <div className="tool-item">
                    <span className={`tool-status ${tool.success ? 'success' : 'error'}`}>
                      {tool.success ? '✓' : '✗'}
                    </span>
                    <span className="tool-name">{tool.name}</span>
                    {tool.system_message && (
                      <span className="tool-details"> - {tool.system_message}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
