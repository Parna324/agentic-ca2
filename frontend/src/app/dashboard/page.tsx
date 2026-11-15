'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, GitPullRequest, ShieldAlert } from 'lucide-react';
import { api } from '@/lib/api';
import type { ReviewSummary } from '@/lib/types';

export default function DashboardPage() {
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  useEffect(() => { api.listReviews().then(setReviews).catch(() => setReviews([])); }, []);
  const approved = reviews.filter((r) => r.merge_decision === 'APPROVE').length;
  const blocked = reviews.filter((r) => r.merge_decision === 'REQUEST_CHANGES').length;
  const critical = reviews.reduce((sum, r) => sum + r.critical_count, 0);
  const cards = [
    ['Total reviews', reviews.length, GitPullRequest],
    ['Approved', approved, CheckCircle2],
    ['Changes requested', blocked, ShieldAlert],
    ['Critical findings', critical, ShieldAlert],
  ] as const;
  return (
    <div className="mx-auto max-w-7xl p-8">
      <div className="flex items-center justify-between">
        <div><p className="text-sm text-indigo-400">Overview</p><h1 className="mt-1 text-3xl font-bold text-white">Review dashboard</h1></div>
        <Link href="/review" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">New review</Link>
      </div>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map(([label, value, Icon]) => <div key={label} className="rounded-xl border border-[#24243a] bg-[#111118] p-5"><Icon className="h-5 w-5 text-indigo-400" /><p className="mt-5 text-sm text-slate-400">{label}</p><p className="mt-1 text-3xl font-bold text-white">{value}</p></div>)}
      </div>
      <div className="mt-8 rounded-xl border border-[#24243a] bg-[#111118]">
        <div className="flex items-center justify-between border-b border-[#24243a] p-5"><h2 className="font-semibold text-white">Recent reviews</h2><Link href="/history" className="text-sm text-indigo-400">View history</Link></div>
        {reviews.length === 0 ? <p className="p-8 text-sm text-slate-500">No reviews yet. Submit a diff to begin.</p> : reviews.slice(0, 8).map((review) => <Link key={review.id} href={`/results/${review.id}`} className="flex items-center justify-between border-b border-[#1d1d2c] px-5 py-4 last:border-0 hover:bg-[#171722]"><div><p className="font-medium text-slate-200">{review.repo_name || 'Untitled repository'}</p><p className="mt-1 text-xs text-slate-500">{new Date(review.created_at).toLocaleString()}</p></div><span className={review.merge_decision === 'APPROVE' ? 'text-emerald-400' : 'text-amber-400'}>{review.merge_decision}</span><ArrowRight className="h-4 w-4 text-slate-600" /></Link>)}
      </div>
    </div>
  );
}
