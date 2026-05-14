import { StrategyManager } from '@/components/strategy-manager';
import { Shell } from '@/components/shell';
import { getStrategies } from '@/lib/api';

export default async function StrategiesPage() {
  const strategies = await getStrategies();

  return (
    <Shell>
      <div className="mb-6 max-w-3xl">
        <h2 className="text-2xl font-semibold">Strategies</h2>
        <p className="mt-2 text-sm text-slate-600">
          Save formal strategy definitions with versions and parameters, then reuse them
          in backtests and match them against your journal trades.
        </p>
      </div>
      <StrategyManager strategies={strategies} />
    </Shell>
  );
}

