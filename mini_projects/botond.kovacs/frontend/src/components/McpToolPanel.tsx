import React, { useState } from 'react';
import { api } from '../api';

export const McpToolPanel: React.FC = () => {
  const [toolName, setToolName] = useState('natural_gas.prices');
  const [argumentsJson, setArgumentsJson] = useState('{"series": "henry_hub_spot", "start": "2023-01-01", "frequency": "daily"}');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleCall = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const args = JSON.parse(argumentsJson);
      const resp = await api.callMcpTool(toolName, args);
      setResult(resp);
    } catch (e: any) {
      setError(e.message || 'Invalid arguments or request failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', padding: 16, margin: 16, borderRadius: 8 }}>
      <h3>MCP Tool Hívó Panel (EIA)</h3>
      <div>
        <label>Tool neve: </label>
        <input value={toolName} onChange={e => setToolName(e.target.value)} style={{ width: 250 }} />
      </div>
      <div style={{ marginTop: 8 }}>
        <label>Argumentumok (JSON):</label>
        <textarea value={argumentsJson} onChange={e => setArgumentsJson(e.target.value)} rows={4} style={{ width: 400 }} />
      </div>
      <button onClick={handleCall} disabled={isLoading} style={{ marginTop: 8 }}>
        {isLoading ? 'Hívás...' : 'Tool hívása'}
      </button>
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
      {result && (
        <pre style={{ background: '#2a2a2a', color: '#e0e0e0', marginTop: 8, padding: 8, maxHeight: 300, overflow: 'auto' }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
};
