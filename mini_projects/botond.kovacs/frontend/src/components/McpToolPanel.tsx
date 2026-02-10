import React, { useState } from 'react';
import { api } from '../api';

export const McpToolPanel: React.FC = () => {
  const [toolName, setToolName] = useState('natural_gas.prices');
  const [startDate, setStartDate] = useState('2025-12-01');
  const [endDate, setEndDate] = useState('2025-12-07');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleCall = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const args = {
        start: startDate,
        end: endDate
      };
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
        <label>Start dátum: </label>
        <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
        <label style={{ marginLeft: 16 }}>End dátum: </label>
        <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
      </div>
      <button onClick={handleCall} disabled={isLoading} style={{ marginTop: 8 }}>
        {isLoading ? 'Hívás...' : 'Tool hívása'}
      </button>
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
      {(() => {
        let dataRows = null;
        if (result && result.response && result.response.data && result.response.data.length > 0) {
          dataRows = result.response.data;
        } else if (result && result.result && result.result.content && result.result.content[0] && result.result.content[0].text) {
          try {
            const parsed = JSON.parse(result.result.content[0].text);
            if (parsed.response && parsed.response.data && parsed.response.data.length > 0) {
              dataRows = parsed.response.data;
            }
          } catch (e) {}
        }
        if (dataRows) {
          return (
            <table style={{ marginTop: 16, borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr style={{ background: '#eee' }}>
                  <th style={{ border: '1px solid #ccc', padding: 8 }}>Dátum</th>
                  <th style={{ border: '1px solid #ccc', padding: 8 }}>Ár (USD/MMBtu)</th>
                </tr>
              </thead>
              <tbody>
                {dataRows.map((row: any) => (
                  <tr key={row.period || row.date}>
                    <td style={{ border: '1px solid #ccc', padding: 8 }}>{row.period || row.date}</td>
                    <td style={{ border: '1px solid #ccc', padding: 8 }}>{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          );
        } else if (result) {
          return (
            <pre style={{ background: '#f8d7da', color: '#721c24', marginTop: 16, padding: 8 }}>
              Nincs megjeleníthető adat vagy hibás a válasz szerkezete.
              {'\n'}Debug: {JSON.stringify(result, null, 2)}
            </pre>
          );
        } else {
          return null;
        }
      })()}
    </div>
  );
};
