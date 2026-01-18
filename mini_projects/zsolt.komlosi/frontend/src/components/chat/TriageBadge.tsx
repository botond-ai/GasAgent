import type { Triage } from '../../types';
import { PRIORITY_CONFIG, SENTIMENT_CONFIG } from '../../types';

interface TriageBadgeProps {
  triage: Triage;
  compact?: boolean;
}

export default function TriageBadge({ triage, compact = false }: TriageBadgeProps) {
  const priorityConfig = PRIORITY_CONFIG[triage.priority];
  const sentimentConfig = SENTIMENT_CONFIG[triage.sentiment];

  const priorityClasses = {
    P1: 'bg-red-100 text-red-800 border-red-200',
    P2: 'bg-orange-100 text-orange-800 border-orange-200',
    P3: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    P4: 'bg-green-100 text-green-800 border-green-200',
  };

  const sentimentClasses = {
    frustrated: 'bg-red-50 text-red-700',
    neutral: 'bg-gray-50 text-gray-700',
    satisfied: 'bg-green-50 text-green-700',
  };

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span
          className={`badge border ${priorityClasses[triage.priority]}`}
        >
          {triage.priority}
        </span>
        <span className="text-sm">{sentimentConfig.icon}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span
        className={`badge border ${priorityClasses[triage.priority]}`}
        title={`Prioritás: ${priorityConfig.label}`}
      >
        {triage.priority} - {priorityConfig.label}
      </span>

      <span className={`badge ${sentimentClasses[triage.sentiment]}`}>
        {sentimentConfig.icon} {sentimentConfig.label}
      </span>

      <span className="badge bg-blue-50 text-blue-700">
        {triage.category}
        {triage.subcategory && ` / ${triage.subcategory}`}
      </span>

      <span className="badge bg-purple-50 text-purple-700">
        SLA: {triage.sla_hours}h
      </span>

      {triage.confidence && (
        <span className="badge bg-gray-100 text-gray-600">
          {Math.round(triage.confidence * 100)}% biztos
        </span>
      )}
    </div>
  );
}
