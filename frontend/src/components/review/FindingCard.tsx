'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, FileCode, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';
import Badge from '@/components/ui/Badge';
import type { Finding } from '@/lib/types';

const severityOrder: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
  INFO: 4,
};

interface FindingCardProps {
  finding: Finding;
  defaultOpen?: boolean;
}

export default function FindingCard({ finding, defaultOpen = false }: FindingCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className={clsx(
        'border rounded-xl overflow-hidden transition-all',
        finding.severity === 'CRITICAL' && 'border-red-500/40',
        finding.severity === 'HIGH' && 'border-orange-500/40',
        finding.severity === 'MEDIUM' && 'border-yellow-500/40',
        finding.severity === 'LOW' && 'border-blue-500/40',
        finding.severity === 'INFO' && 'border-gray-500/40',
        'bg-[#111118]'
      )}
    >
      {/* Header */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-[#1a1a28] transition-colors"
      >
        <AlertCircle
          className={clsx(
            'w-4 h-4 mt-0.5 flex-shrink-0',
            finding.severity === 'CRITICAL' && 'text-red-400',
            finding.severity === 'HIGH' && 'text-orange-400',
            finding.severity === 'MEDIUM' && 'text-yellow-400',
            finding.severity === 'LOW' && 'text-blue-400',
            finding.severity === 'INFO' && 'text-gray-400'
          )}
        />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <Badge label={finding.severity} />
            <Badge label={finding.category} variant="INFO" />
            <span className="text-[#6b7280] text-xs">{finding.agent}</span>
          </div>
          <div className="text-sm font-medium text-slate-100">{finding.title}</div>
          <div className="flex items-center gap-1 mt-1">
            <FileCode className="w-3 h-3 text-[#4b5563]" />
            <span className="text-xs text-[#6b7280]">
              {finding.file}
              {finding.line !== undefined && `:${finding.line}`}
            </span>
          </div>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-[#4b5563] flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-[#4b5563] flex-shrink-0" />
        )}
      </button>

      {/* Body */}
      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-[#1e1e2e] pt-3">
          <div>
            <div className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider mb-1">
              Description
            </div>
            <p className="text-sm text-slate-300">{finding.description}</p>
          </div>

          {finding.evidence && (
            <div>
              <div className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider mb-1">
                Evidence
              </div>
              <pre className="bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg p-3 text-xs font-mono text-green-300 overflow-x-auto scrollbar-thin whitespace-pre-wrap">
                {finding.evidence}
              </pre>
            </div>
          )}

          <div>
            <div className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider mb-1">
              Recommendation
            </div>
            <p className="text-sm text-indigo-300">{finding.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export { severityOrder };
