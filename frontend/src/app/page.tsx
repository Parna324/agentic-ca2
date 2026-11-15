import Link from 'next/link';
import { ArrowRight, Bot, GitPullRequest, ShieldCheck, Sparkles } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-full">
      <section className="mx-auto max-w-6xl px-8 py-24">
        <div className="max-w-3xl">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">
            <Sparkles className="h-3.5 w-3.5" /> Offline-first multi-agent review
          </div>
          <h1 className="text-5xl font-bold tracking-tight text-white">
            A review board for every code change.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-400">
            Submit a diff and let independent agents inspect correctness, security, style, and
            test coverage before a manager makes a deterministic merge recommendation.
          </p>
          <Link href="/review" className="mt-8 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-500">
            Start a review <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="mt-20 grid gap-4 md:grid-cols-3">
          {[
            [Bot, 'Specialist agents', 'Four focused analyzers fan out from a shared change state.'],
            [ShieldCheck, 'Actionable findings', 'Evidence, severity, recommendations, and advisory patches.'],
            [GitPullRequest, 'Auditable decisions', 'Every run is saved with agent activity and an append-only trace.'],
          ].map(([Icon, title, description]) => (
            <div key={title as string} className="rounded-xl border border-[#24243a] bg-[#111118] p-5">
              <Icon className="h-5 w-5 text-indigo-400" />
              <h2 className="mt-4 font-semibold text-white">{title as string}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">{description as string}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
