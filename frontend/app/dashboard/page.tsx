import { AiPanel } from '@/components/ai-panel';
import { EquityCurve } from '@/components/equity-curve';
import { Shell } from '@/components/shell';
import { StatCard } from '@/components/stat-card';
import { WinRateChart } from '@/components/win-rate-chart';
import { getAiAnalysis, getAnalytics } from '@/lib/api';

export default async function DashboardPage() {
  const [analytics, analysis] = await Promise.all([getAnalytics(), getAiAnalysis()]);

  return (
    <Shell>
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          label="Total profit"
          value={`${analytics.totalProfit.toFixed(2)}`}
          hint="Sum of all recorded trade outcomes."
        />
        <StatCard
          label="Profit factor"
          value={analytics.profitFactor.toFixed(2)}
          hint="Gross profit divided by gross loss."
        />
        <StatCard
          label="Average RR"
          value={analytics.averageRiskReward.toFixed(2)}
          hint="Average planned risk-reward ratio."
        />
        <StatCard
          label="Best setup"
          value={analytics.bestSetup ?? 'N/A'}
          hint="Highest win-rate setup in your journal."
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr,0.9fr]">
        <div className="space-y-6">
          <WinRateChart winRate={analytics.winRate} />
          <EquityCurve points={analytics.equityCurve} />
        </div>
        <AiPanel analysis={analysis} />
      </div>
    </Shell>
  );
}
