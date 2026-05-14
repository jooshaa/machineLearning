import Link from 'next/link';
import { ReactNode } from 'react';

const navItems = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/trades', label: 'Trades' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/strategies', label: 'Strategies' },
  { href: '/backtests', label: 'Backtests' },
];

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8 flex flex-col gap-6 rounded-3xl bg-ink px-6 py-6 text-white shadow-xl">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-teal-200">
              Trading Journal
            </p>
            <h1 className="text-3xl font-semibold">AI performance lab</h1>
          </div>
          <p className="max-w-2xl text-sm text-slate-300">
            Track execution quality, review your risk profile, and surface repeatable
            edges from your own journal data.
          </p>
        </div>
        <nav className="flex flex-wrap gap-3">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-full border border-white/15 px-4 py-2 text-sm text-slate-100 transition hover:border-teal-300 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      {children}
    </div>
  );
}
