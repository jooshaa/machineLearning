import { AiAnalysis } from '@/lib/types';

export function AiPanel({ analysis }: { analysis: AiAnalysis | null }) {
  if (!analysis) {
    return (
      <div className="card p-5">
        <h2 className="text-lg font-semibold">AI panel</h2>
        <p className="mt-4 text-sm text-slate-500">
          Add at least 5 trades with both wins and losses to unlock model analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">AI panel</h2>
          <p className="mt-1 text-sm text-slate-500">
            Model sample size: {analysis.sample_size} trades
          </p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-4 py-3 text-right">
          <p className="text-sm text-slate-500">Win probability</p>
          <p className="text-2xl font-semibold text-sea">{analysis.win_probability}%</p>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Risk score</p>
          <p className="mt-2 text-2xl font-semibold text-coral">{analysis.risk_score}%</p>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Top driver</p>
          <p className="mt-2 text-lg font-semibold">
            {analysis.feature_importance[0]?.feature ?? 'Not enough variance'}
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Best setup</p>
          <p className="mt-2 text-lg font-semibold capitalize">
            {analysis.best_setup ?? 'Not enough data'}
          </p>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Worst session</p>
          <p className="mt-2 text-lg font-semibold">
            {analysis.worst_session ?? 'Not enough data'}
          </p>
        </div>
      </div>
      <div className="mt-5 space-y-3">
        {analysis.insights.map((insight) => (
          <div key={insight} className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">{insight}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-2xl bg-slate-50 p-4">
        <p className="text-sm text-slate-500">Model holdout evaluation</p>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Metric label="Accuracy" value={analysis.evaluation.accuracy} />
          <Metric label="Precision" value={analysis.evaluation.precision} />
          <Metric label="Recall" value={analysis.evaluation.recall} />
          <Metric label="ROC-AUC" value={analysis.evaluation.roc_auc} />
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Split: {analysis.evaluation.split_type}
          {analysis.evaluation.train_end_date
            ? `, train through ${new Date(analysis.evaluation.train_end_date).toLocaleDateString()}`
            : ''}
          {analysis.evaluation.test_start_date
            ? `, test from ${new Date(analysis.evaluation.test_start_date).toLocaleDateString()}`
            : ''}
        </p>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold">
        {value === null ? 'N/A' : value.toFixed(3)}
      </p>
    </div>
  );
}
