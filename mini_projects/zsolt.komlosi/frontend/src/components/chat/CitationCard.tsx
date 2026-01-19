import { FileText, ExternalLink } from 'lucide-react';
import type { Citation } from '../../types';

interface CitationCardProps {
  citation: Citation;
  expanded?: boolean;
}

export default function CitationCard({ citation, expanded = false }: CitationCardProps) {
  const scorePercent = Math.round(citation.score * 100);
  const scoreColor =
    scorePercent >= 80
      ? 'text-green-600 bg-green-50'
      : scorePercent >= 60
      ? 'text-yellow-600 bg-yellow-50'
      : 'text-gray-600 bg-gray-50';

  return (
    <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 hover:border-gray-200 transition-colors">
      <div className="flex items-start gap-2">
        <div className="flex-shrink-0 p-1.5 bg-white rounded border border-gray-200">
          <FileText className="w-4 h-4 text-gray-500" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-primary-600 bg-primary-50 px-1.5 py-0.5 rounded">
              [{citation.id}]
            </span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${scoreColor}`}>
              {scorePercent}%
            </span>
          </div>

          <h4 className="text-sm font-medium text-gray-900 mt-1 truncate">
            {citation.title}
          </h4>

          <p className="text-xs text-gray-500 mt-0.5">{citation.doc_id}</p>

          {expanded && citation.excerpt && (
            <p className="text-sm text-gray-600 mt-2 line-clamp-3">
              "{citation.excerpt}"
            </p>
          )}
        </div>

        <button className="flex-shrink-0 p-1 text-gray-400 hover:text-gray-600 transition-colors">
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
