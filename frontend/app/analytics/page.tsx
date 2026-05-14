import { EquityCurve } from '@/components/equity-curve';
import { Shell } from '@/components/shell';
import { StatCard } from '@/components/stat-card';
import { getAiAnalysis, getAnalytics } from '@/lib/api';

export default async function AnalyticsPage() {
  const [analytics, analysis] = await Promise.all([getAnalytics(), getAiAnalysis()]);

  return (
    <Shell>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Win rate"
          value={`${analytics.winRate.toFixed(1)}%`}
          hint="Percentage of completed trades marked as wins."
        />
        <StatCard
          label="Total trades"
          value={String(analytics.totalTrades)}
          hint="Current sample size in the journal."
        />
        <StatCard
          label="Avg confidence"
          value={analytics.averageConfidence.toFixed(2)}
          hint="Average self-rated conviction score."
        />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr,0.9fr]">
        <EquityCurve points={analytics.equityCurve} />
        <div className="card p-5">
          <h2 className="text-lg font-semibold">AI insights</h2>
          <div className="mt-5 space-y-3">
            {(analysis?.insights ?? ['No AI insights available yet.']).map((insight) => (
              <div key={insight} className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
                {insight}
              </div>
            ))}
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Weakest session</p>
              <p className="mt-2 text-lg font-semibold">{analytics.weakestSession ?? 'N/A'}</p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Best pair</p>
              <p className="mt-2 text-lg font-semibold">{analytics.bestPair ?? 'N/A'}</p>
            </div>
          </div>
          <div className="mt-5">
            <p className="text-sm text-slate-500">Common mistakes</p>
            <div className="mt-3 space-y-2">
              {(analytics.commonMistakes.length > 0
                ? analytics.commonMistakes
                : [{ label: 'No mistake tags yet', count: 0 }]
              ).map((mistake) => (
                <div
                  key={mistake.label}
                  className="flex items-center justify-between rounded-2xl border border-slate-200 px-4 py-3 text-sm"
                >
                  <span>{mistake.label}</span>
                  <span className="font-medium text-slate-500">{mistake.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
