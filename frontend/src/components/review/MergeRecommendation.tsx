import { CheckCircle2, XCircle, Clock } from 'lucide-react';
import type { ReviewDetail } from '@/lib/types';

interface MergeRecommendationProps {
  review: ReviewDetail;
}

export default function MergeRecommendation({ review }: MergeRecommendationProps) {
  const { merge_decision, decision_reason, critical_count, high_count } = review;

  if (merge_decision === 'APPROVE') {
    return (
      <div className="rounded-xl border border-green-500/40 bg-green-500/10 p-6 flex items-start gap-4">
        <CheckCircle2 className="w-10 h-10 text-green-400 flex-shrink-0 mt-0.5" />
        <div>
          <div className="text-green-400 text-xl font-bold mb-1">✅ Approved to Merge</div>
          {decision_reason && (
            <p className="text-slate-300 text-sm mb-3">{decision_reason}</p>
          )}
          <div className="flex gap-3 text-xs text-green-300">
            <span>Critical: {critical_count}</span>
            <span>High: {high_count}</span>
          </div>
        </div>
      </div>
    );
  }

  if (merge_decision === 'REQUEST_CHANGES') {
    return (
      <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-6 flex items-start gap-4">
        <XCircle className="w-10 h-10 text-red-400 flex-shrink-0 mt-0.5" />
        <div>
          <div className="text-red-400 text-xl font-bold mb-1">❌ Changes Requested</div>
          {decision_reason && (
            <p className="text-slate-300 text-sm mb-3">{decision_reason}</p>
          )}
          <div className="flex gap-3 text-xs text-red-300">
            <span className="font-semibold">Critical: {critical_count}</span>
            <span className="font-semibold">High: {high_count}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/10 p-6 flex items-start gap-4">
      <Clock className="w-10 h-10 text-yellow-400 flex-shrink-0 mt-0.5" />
      <div>
        <div className="text-yellow-400 text-xl font-bold mb-1">⏳ Review Pending</div>
        <p className="text-slate-300 text-sm">Analysis is in progress...</p>
      </div>
    </div>
  );
}
