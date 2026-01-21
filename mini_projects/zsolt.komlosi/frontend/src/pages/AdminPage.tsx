import { useState, useEffect } from 'react';
import {
  Upload,
  Link as LinkIcon,
  FileText,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Loader2,
  Search,
} from 'lucide-react';
import type { Document } from '../types';
import api from '../services/api';

type TabType = 'documents' | 'upload';

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<TabType>('documents');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Upload form state
  const [uploadType, setUploadType] = useState<'file' | 'url'>('file');
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
    } catch (err) {
      setError('Nem sikerült betölteni a dokumentumokat');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!title.trim()) {
      setError('A cím megadása kötelező');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (uploadType === 'file' && file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        await api.uploadDocument(formData);
      } else if (uploadType === 'url' && url) {
        await api.indexUrl(url, title);
      } else {
        setError('Válasszon fájlt vagy adjon meg URL-t');
        return;
      }

      setSuccess('Dokumentum sikeresen feltöltve és indexelve');
      setTitle('');
      setUrl('');
      setFile(null);
      loadDocuments();
      setActiveTab('documents');
    } catch (err) {
      setError('Hiba történt a feltöltés során');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (documentId: string) => {
    if (!confirm('Biztosan törli ezt a dokumentumot?')) return;

    setIsLoading(true);
    try {
      await api.deleteDocument(documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
      setSuccess('Dokumentum törölve');
    } catch (err) {
      setError('Nem sikerült törölni a dokumentumot');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReindex = async (documentId: string) => {
    setIsLoading(true);
    try {
      await api.reindexDocument(documentId);
      setSuccess('Dokumentum újraindexelve');
      loadDocuments();
    } catch (err) {
      setError('Nem sikerült újraindexelni');
    } finally {
      setIsLoading(false);
    }
  };

  const filteredDocuments = documents.filter(
    (doc) =>
      doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.source_type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sourceTypeIcon = (type: string) => {
    switch (type) {
      case 'markdown':
        return 'MD';
      case 'pdf':
        return 'PDF';
      case 'docx':
        return 'DOC';
      case 'web':
        return 'WEB';
      default:
        return '?';
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 bg-white border-b border-gray-200">
        <h1 className="text-xl font-semibold text-gray-900">Dokumentum Kezelés</h1>
        <p className="text-sm text-gray-500 mt-1">
          Tudásbázis dokumentumok feltöltése és kezelése
        </p>
      </div>

      {/* Tabs */}
      <div className="px-6 py-2 bg-white border-b border-gray-200">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab('documents')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === 'documents'
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <FileText className="w-4 h-4 inline-block mr-2" />
            Dokumentumok ({documents.length})
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === 'upload'
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Upload className="w-4 h-4 inline-block mr-2" />
            Feltöltés
          </button>
        </div>
      </div>

      {/* Notifications */}
      {(error || success) && (
        <div className="px-6 pt-4">
          {error && (
            <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-red-800 mb-2">
              <AlertCircle className="w-5 h-5" />
              <span className="text-sm">{error}</span>
              <button onClick={() => setError(null)} className="ml-auto">
                ×
              </button>
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 px-4 py-3 bg-green-50 border border-green-200 rounded-lg text-green-800 mb-2">
              <CheckCircle className="w-5 h-5" />
              <span className="text-sm">{success}</span>
              <button onClick={() => setSuccess(null)} className="ml-auto">
                ×
              </button>
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'documents' && (
          <div>
            {/* Search */}
            <div className="mb-4">
              <div className="relative">
                <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Dokumentum keresése..."
                  className="input pl-10"
                />
              </div>
            </div>

            {/* Document List */}
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">Nincsenek dokumentumok</p>
                <button
                  onClick={() => setActiveTab('upload')}
                  className="mt-4 btn btn-primary"
                >
                  Új dokumentum feltöltése
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredDocuments.map((doc) => (
                  <div
                    key={doc.id}
                    className="card p-4 flex items-center gap-4"
                  >
                    <div className="flex-shrink-0 w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center font-mono text-sm text-gray-600">
                      {sourceTypeIcon(doc.source_type)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-gray-900 truncate">
                        {doc.title}
                      </h3>
                      <div className="flex items-center gap-3 text-sm text-gray-500 mt-1">
                        <span>{doc.chunk_count} chunk</span>
                        <span>•</span>
                        <span>
                          {new Date(doc.indexed_at).toLocaleDateString('hu-HU')}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleReindex(doc.id)}
                        className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                        title="Újraindexelés"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Törlés"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="max-w-xl">
            <div className="card p-6">
              {/* Upload Type Toggle */}
              <div className="flex gap-2 mb-6">
                <button
                  onClick={() => setUploadType('file')}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    uploadType === 'file'
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <Upload className="w-5 h-5" />
                  <span>Fájl feltöltés</span>
                </button>
                <button
                  onClick={() => setUploadType('url')}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    uploadType === 'url'
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <LinkIcon className="w-5 h-5" />
                  <span>URL indexelés</span>
                </button>
              </div>

              {/* Title */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Dokumentum címe *
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="pl. Felhasználói Útmutató"
                  className="input"
                />
              </div>

              {/* File Upload */}
              {uploadType === 'file' && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Fájl kiválasztása
                  </label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                    <input
                      type="file"
                      accept=".md,.pdf,.docx,.txt"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                      className="hidden"
                      id="file-upload"
                    />
                    <label
                      htmlFor="file-upload"
                      className="cursor-pointer"
                    >
                      <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                      {file ? (
                        <p className="text-sm text-gray-900">{file.name}</p>
                      ) : (
                        <>
                          <p className="text-sm text-gray-600">
                            Kattintson vagy húzza ide a fájlt
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            MD, PDF, DOCX, TXT (max 10MB)
                          </p>
                        </>
                      )}
                    </label>
                  </div>
                </div>
              )}

              {/* URL Input */}
              {uploadType === 'url' && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Weboldal URL
                  </label>
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example.com/docs"
                    className="input"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    A weboldal tartalma automatikusan le lesz töltve és indexelve
                  </p>
                </div>
              )}

              {/* Submit */}
              <button
                onClick={handleUpload}
                disabled={isLoading || !title.trim()}
                className="w-full btn btn-primary flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Feldolgozás...</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-5 h-5" />
                    <span>Feltöltés és indexelés</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
