export function EquityCurve({
  points,
}: {
  points: Array<{ index: number; equity: number }>;
}) {
  const width = 520;
  const height = 220;

  if (points.length === 0) {
    return (
      <div className="card p-5">
        <h2 className="text-lg font-semibold">Equity curve</h2>
        <p className="mt-4 text-sm text-slate-500">Add trades to visualize performance.</p>
      </div>
    );
  }

  const minEquity = Math.min(...points.map((point) => point.equity));
  const maxEquity = Math.max(...points.map((point) => point.equity));
  const range = maxEquity - minEquity || 1;

  const path = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      const y = height - ((point.equity - minEquity) / range) * height;
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Equity curve</h2>
        <span className="text-sm text-slate-500">{points.length} trades</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        <path d={path} fill="none" stroke="#0f766e" strokeWidth="4" strokeLinecap="round" />
      </svg>
    </div>
  );
}

