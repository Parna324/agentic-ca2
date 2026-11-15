'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, GitPullRequest, History, Settings, Shield } from 'lucide-react';
import { clsx } from 'clsx';

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/review', label: 'New Review', icon: GitPullRequest },
  { href: '/history', label: 'History', icon: History },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 flex-shrink-0 bg-[#111118] border-r border-[#1e1e2e] flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-[#1e1e2e]">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center group-hover:bg-indigo-500 transition-colors">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-white font-bold text-sm leading-tight">CR Board</div>
            <div className="text-[#6b7280] text-[10px] leading-tight">AI Code Review</div>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                active
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                  : 'text-[#9ca3af] hover:text-white hover:bg-[#1e1e2e]'
              )}
            >
              <Icon className={clsx('w-4 h-4', active ? 'text-indigo-400' : '')} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-[#1e1e2e]">
        <div className="text-[#4b5563] text-xs">Multi-Agent Analysis v1.0</div>
      </div>
    </aside>
  );
}
