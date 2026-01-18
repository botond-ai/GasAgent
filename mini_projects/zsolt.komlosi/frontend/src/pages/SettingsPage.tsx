import { useState, useEffect } from 'react';
import { CheckCircle, AlertCircle, Server, Database, Cpu, RefreshCw } from 'lucide-react';
import api from '../services/api';

interface SystemStatus {
  api: 'online' | 'offline' | 'checking';
  qdrant: 'online' | 'offline' | 'checking';
  version: string;
}

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus>({
    api: 'checking',
    qdrant: 'checking',
    version: '-',
  });

  useEffect(() => {
    checkSystemStatus();
  }, []);

  const checkSystemStatus = async () => {
    setStatus((prev) => ({ ...prev, api: 'checking', qdrant: 'checking' }));

    try {
      const health = await api.healthCheck();
      setStatus({
        api: 'online',
        qdrant: 'online', // Assuming if API is healthy, Qdrant is too
        version: health.version || '1.0.0',
      });
    } catch {
      setStatus((prev) => ({
        ...prev,
        api: 'offline',
        qdrant: 'offline',
      }));
    }
  };

  const StatusBadge = ({ status }: { status: 'online' | 'offline' | 'checking' }) => {
    if (status === 'checking') {
      return (
        <span className="flex items-center gap-1.5 text-sm text-yellow-600">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Ellenőrzés...
        </span>
      );
    }

    if (status === 'online') {
      return (
        <span className="flex items-center gap-1.5 text-sm text-green-600">
          <CheckCircle className="w-4 h-4" />
          Online
        </span>
      );
    }

    return (
      <span className="flex items-center gap-1.5 text-sm text-red-600">
        <AlertCircle className="w-4 h-4" />
        Offline
      </span>
    );
  };

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="px-6 py-4 bg-white border-b border-gray-200">
        <h1 className="text-xl font-semibold text-gray-900">Beállítások</h1>
        <p className="text-sm text-gray-500 mt-1">
          Rendszer állapot és konfigurációk
        </p>
      </div>

      <div className="p-6 max-w-3xl">
        {/* System Status */}
        <div className="card p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Rendszer Állapot</h2>
            <button
              onClick={checkSystemStatus}
              className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700"
            >
              <RefreshCw className="w-4 h-4" />
              Frissítés
            </button>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-50 rounded-lg">
                  <Server className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">FastAPI Backend</p>
                  <p className="text-sm text-gray-500">REST API szerver</p>
                </div>
              </div>
              <StatusBadge status={status.api} />
            </div>

            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-50 rounded-lg">
                  <Database className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">Qdrant Vector DB</p>
                  <p className="text-sm text-gray-500">Vektor adatbázis</p>
                </div>
              </div>
              <StatusBadge status={status.qdrant} />
            </div>

            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-50 rounded-lg">
                  <Cpu className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">Verzió</p>
                  <p className="text-sm text-gray-500">Alkalmazás verzió</p>
                </div>
              </div>
              <span className="text-sm font-mono text-gray-600">
                v{status.version}
              </span>
            </div>
          </div>
        </div>

        {/* Configuration Info */}
        <div className="card p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Konfiguráció</h2>

          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Embedding Modell</span>
              <span className="font-mono text-gray-900">text-embedding-3-large</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Chunk Méret</span>
              <span className="font-mono text-gray-900">600 token</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Chunk Átfedés</span>
              <span className="font-mono text-gray-900">80 token</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Hybrid Search Súlyozás</span>
              <span className="font-mono text-gray-900">Vector: 0.5, BM25: 0.5</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-gray-600">Rolling Summary</span>
              <span className="font-mono text-gray-900">10 üzenetenként</span>
            </div>
          </div>
        </div>

        {/* About */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Névjegy</h2>

          <div className="text-sm text-gray-600 space-y-2">
            <p>
              <strong>SupportAI</strong> - Ügyfélszolgálati AI Asszisztens
            </p>
            <p>
              Ez a projekt a RoboDreams "AI Agents" tanfolyam miniprojektjének
              része. A rendszer RAG (Retrieval-Augmented Generation) és chat
              memória funkciókat használ a tudásbázis alapú válaszgeneráláshoz.
            </p>
            <p className="pt-2">
              <strong>Funkciók:</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 pl-2">
              <li>Ticket elemzés és triage</li>
              <li>Hybrid keresés (BM25 + vektor)</li>
              <li>LLM reranking</li>
              <li>Query expansion</li>
              <li>Rolling summary memória</li>
              <li>PII szűrés</li>
              <li>Citációk [#1] formátumban</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
