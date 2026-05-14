export function WinRateChart({ winRate }: { winRate: number }) {
  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Win rate</h2>
        <span className="text-sm text-slate-500">{winRate.toFixed(1)}%</span>
      </div>
      <div className="h-4 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-sea transition-all"
          style={{ width: `${Math.max(0, Math.min(winRate, 100))}%` }}
        />
      </div>
      <p className="mt-4 text-sm text-slate-500">
        This chart summarizes how often your journaled setups finish green.
      </p>
    </div>
  );
}

