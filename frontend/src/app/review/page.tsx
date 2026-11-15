'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

const sample = `--- a/example.py
+++ b/example.py
@@ -1,3 +1,8 @@
+import subprocess
+
+def run_command(user_input):
+    password = "supersecret"
+    return subprocess.run(user_input, shell=True)
`;

export default function NewReviewPage() {
  const router = useRouter();
  const [diff, setDiff] = useState(sample);
  const [repo, setRepo] = useState('demo-repository');
  const [language, setLanguage] = useState('python');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError('');
    try { const review = await api.createReview({ diff_text: diff, repo_name: repo, language, submission_type: 'diff' }); router.push(`/results/${review.id}`); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to start review'); setLoading(false); }
  }
  return <div className="mx-auto max-w-5xl p-8"><p className="text-sm text-indigo-400">Analysis workspace</p><h1 className="mt-1 text-3xl font-bold text-white">New code review</h1><p className="mt-2 text-slate-400">Paste a unified Git diff. Analysis runs in deterministic offline mode by default.</p><form onSubmit={submit} className="mt-8 space-y-5"><div className="grid gap-5 md:grid-cols-2"><label className="text-sm text-slate-300">Repository<input value={repo} onChange={(e) => setRepo(e.target.value)} className="mt-2 w-full rounded-lg border border-[#2b2b42] bg-[#111118] px-3 py-2 text-white outline-none focus:border-indigo-500" /></label><label className="text-sm text-slate-300">Language<select value={language} onChange={(e) => setLanguage(e.target.value)} className="mt-2 w-full rounded-lg border border-[#2b2b42] bg-[#111118] px-3 py-2 text-white outline-none"><option value="python">Python</option><option value="javascript">JavaScript</option><option value="typescript">TypeScript</option></select></label></div><label className="block text-sm text-slate-300">Git diff<textarea required value={diff} onChange={(e) => setDiff(e.target.value)} rows={18} className="mt-2 w-full rounded-lg border border-[#2b2b42] bg-[#0d0d14] p-4 font-mono text-sm text-slate-200 outline-none focus:border-indigo-500" /></label>{error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}<button disabled={loading} className="rounded-lg bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">{loading ? 'Starting agents...' : 'Start review'}</button></form></div>;
}
