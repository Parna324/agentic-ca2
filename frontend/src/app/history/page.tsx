'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { ReviewSummary } from '@/lib/types';
export default function HistoryPage() { const [reviews, setReviews] = useState<ReviewSummary[]>([]); useEffect(() => { api.listReviews().then(setReviews).catch(() => setReviews([])); }, []); return <div className="mx-auto max-w-7xl p-8"><h1 className="text-3xl font-bold text-white">Review history</h1><div className="mt-8 overflow-hidden rounded-xl border border-[#24243a] bg-[#111118]">{reviews.map((r) => <Link key={r.id} href={`/results/${r.id}`} className="flex items-center justify-between border-b border-[#1d1d2c] p-5 hover:bg-[#171722]"><div><p className="font-medium text-slate-200">{r.repo_name || 'Untitled repository'}</p><p className="text-xs text-slate-500">{new Date(r.created_at).toLocaleString()} · {r.total_findings} findings</p></div><span className={r.merge_decision === 'APPROVE' ? 'text-emerald-400' : 'text-amber-400'}>{r.status === 'COMPLETED' ? r.merge_decision : r.status}</span></Link>)}{reviews.length === 0 && <p className="p-8 text-slate-500">No saved reviews.</p>}</div></div>; }
