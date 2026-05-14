import { BacktestLab } from '@/components/backtest-lab';
import { AdvancedBacktest } from '@/components/advanced-backtest';
import { Shell } from '@/components/shell';
import { getStrategies } from '@/lib/api';
import { BacktestTabs } from '@/components/backtest-tabs';

export default async function BacktestsPage() {
  const strategies = await getStrategies();

  return (
    <Shell>
      <div className="mb-6 max-w-3xl">
        <h2 className="text-2xl font-semibold">Strategy lab</h2>
        <p className="mt-2 text-sm text-slate-600">
          Backtest your trading strategies on historical OHLCV data. Use the
          simple rule-based backtester or the advanced indicator-driven engine
          with auto data fetching from Yahoo Finance.
        </p>
      </div>
      <BacktestTabs
        simpleContent={<BacktestLab strategies={strategies} />}
        advancedContent={<AdvancedBacktest />}
      />
    </Shell>
  );
}
