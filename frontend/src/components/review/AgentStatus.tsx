import { clsx } from 'clsx';
import { CheckCircle2, XCircle, Clock, Loader2, Wrench, AlertTriangle } from 'lucide-react';
import type { AgentExecution } from '@/lib/types';
import Badge from '@/components/ui/Badge';

interface AgentStatusProps {
  agents: AgentExecution[];
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'COMPLETED') return <CheckCircle2 className="w-4 h-4 text-green-400" />;
  if (status === 'FAILED') return <XCircle className="w-4 h-4 text-red-400" />;
  if (status === 'RUNNING') return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
  return <Clock className="w-4 h-4 text-yellow-400" />;
}

function formatDuration(secs?: number): string {
  if (secs === undefined || secs === null) return '—';
  if (secs < 60) return `${secs.toFixed(1)}s`;
  return `${Math.floor(secs / 60)}m ${(secs % 60).toFixed(0)}s`;
}

export default function AgentStatus({ agents }: AgentStatusProps) {
  if (!agents || agents.length === 0) {
    return (
      <div className="text-center py-8 text-[#6b7280] text-sm">No agent data available.</div>
    );
  }

  return (
    <div className="space-y-3">
      {agents.map((agent) => (
        <div
          key={agent.id}
          className={clsx(
            'bg-[#111118] border rounded-xl p-4',
            agent.status === 'FAILED' ? 'border-red-500/40' : 'border-[#1e1e2e]'
          )}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <StatusIcon status={agent.status} />
              <span className="font-medium text-sm text-slate-100">{agent.agent_name}</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge label={agent.status} />
              <span className="text-xs text-[#6b7280]">{formatDuration(agent.duration_seconds)}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs mb-3">
            <div>
              <span className="text-[#6b7280]">Findings: </span>
              <span className="text-slate-300 font-medium">{agent.findings_count}</span>
            </div>
            {agent.started_at && (
              <div>
                <span className="text-[#6b7280]">Started: </span>
                <span className="text-slate-300">
                  {new Date(agent.started_at).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>

          {agent.tools_invoked && agent.tools_invoked.length > 0 && (
            <div>
              <div className="flex items-center gap-1 mb-1.5">
                <Wrench className="w-3 h-3 text-[#6b7280]" />
                <span className="text-xs text-[#6b7280]">Tools invoked:</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {agent.tools_invoked.map((tool, i) => (
                  <span
                    key={i}
                    className="px-1.5 py-0.5 bg-indigo-500/10 border border-indigo-500/20 rounded text-xs text-indigo-300 font-mono"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {agent.error_message && (
            <div className="mt-2 flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-2">
              <AlertTriangle className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
              <span className="text-xs text-red-300">{agent.error_message}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
