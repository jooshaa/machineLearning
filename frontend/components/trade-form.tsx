'use client';

import { FormEvent, useState } from 'react';
import { createTrade, uploadTradeScreenshots } from '@/lib/api';
import { CreateTradePayload } from '@/lib/types';

type CreateTradeInput = CreateTradePayload;
type NumericField =
  | 'entryPrice'
  | 'stopLoss'
  | 'takeProfit'
  | 'riskReward'
  | 'profit';

const numericFields: Array<{ key: NumericField; label: string }> = [
  { key: 'entryPrice', label: 'Entry' },
  { key: 'stopLoss', label: 'Stop loss' },
  { key: 'takeProfit', label: 'Take profit' },
  { key: 'riskReward', label: 'Risk reward' },
  { key: 'profit', label: 'Profit' },
];

const initialState: CreateTradeInput = {
  pair: 'EURUSD',
  strategyVersion: 'v1',
  timeframe: 'M15',
  session: 'London',
  setup: 'breakout',
  direction: 'buy',
  entryPrice: 1.1,
  stopLoss: 1.095,
  takeProfit: 1.11,
  riskReward: 2,
  result: 'win',
  confidence: 3,
  confluence: 2,
  emotion: 'calm',
  mistake: '',
  notes: '',
  screenshotUrls: [],
  profit: 120,
};

export function TradeForm() {
  const [formData, setFormData] = useState(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [screenshotFiles, setScreenshotFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);

    let screenshotUrls = formData.screenshotUrls;
    if (screenshotFiles.length > 0) {
      setUploadStatus('Uploading screenshots...');
      const uploaded = await uploadTradeScreenshots(screenshotFiles);
      screenshotUrls = uploaded.urls;
    }

    await createTrade({
      ...formData,
      screenshotUrls,
    });
    window.location.reload();
  };

  return (
    <form onSubmit={handleSubmit} className="card grid gap-4 p-5 md:grid-cols-3">
      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Pair</span>
        <input
          required
          type="text"
          value={formData.pair}
          onChange={(event) =>
            setFormData((current) => ({ ...current, pair: event.target.value }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        />
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Strategy version</span>
        <input
          required
          type="text"
          value={formData.strategyVersion}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              strategyVersion: event.target.value,
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        />
      </label>

      {numericFields.map((field) => (
        <label key={field.key} className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">{field.label}</span>
          <input
            required
            type="number"
            step="0.01"
            value={formData[field.key]}
            onChange={(event) =>
              setFormData((current) => ({
                ...current,
                [field.key]: Number(event.target.value),
              }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
      ))}

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Session</span>
        <select
          value={formData.session}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              session: event.target.value as CreateTradeInput['session'],
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        >
          <option value="London">London</option>
          <option value="NY">NY</option>
          <option value="Asia">Asia</option>
        </select>
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Timeframe</span>
        <select
          value={formData.timeframe ?? 'M15'}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              timeframe: event.target.value as CreateTradeInput['timeframe'],
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        >
          <option value="M5">M5</option>
          <option value="M15">M15</option>
          <option value="H1">H1</option>
          <option value="H4">H4</option>
          <option value="D1">D1</option>
        </select>
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Setup</span>
        <select
          value={formData.setup}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              setup: event.target.value as CreateTradeInput['setup'],
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        >
          <option value="breakout">Breakout</option>
          <option value="pullback">Pullback</option>
          <option value="reversal">Reversal</option>
        </select>
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Direction</span>
        <select
          value={formData.direction}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              direction: event.target.value as CreateTradeInput['direction'],
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        >
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Result</span>
        <select
          value={formData.result}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              result: event.target.value as CreateTradeInput['result'],
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        >
          <option value="win">Win</option>
          <option value="loss">Loss</option>
        </select>
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Confidence</span>
        <input
          type="number"
          min="1"
          max="5"
          value={formData.confidence}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              confidence: Number(event.target.value),
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        />
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Confluence</span>
        <input
          type="number"
          min="1"
          max="5"
          value={formData.confluence}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              confluence: Number(event.target.value),
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        />
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="text-slate-500">Emotion</span>
        <select
          value={formData.emotion ?? 'neutral'}
          onChange={(event) =>
            setFormData((current) => ({
              ...current,
              emotion: event.target.value as CreateTradeInput['emotion'],
            }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        >
          <option value="calm">Calm</option>
          <option value="confident">Confident</option>
          <option value="hesitant">Hesitant</option>
          <option value="fearful">Fearful</option>
          <option value="revenge">Revenge</option>
          <option value="neutral">Neutral</option>
        </select>
      </label>

      <label className="flex flex-col gap-2 text-sm md:col-span-2">
        <span className="text-slate-500">Mistake tag</span>
        <input
          type="text"
          value={formData.mistake ?? ''}
          onChange={(event) =>
            setFormData((current) => ({ ...current, mistake: event.target.value }))
          }
          className="rounded-xl border border-slate-300 px-4 py-2"
        />
      </label>

      <label className="flex flex-col gap-2 text-sm md:col-span-3">
        <span className="text-slate-500">Notes</span>
        <textarea
          value={formData.notes ?? ''}
          onChange={(event) =>
            setFormData((current) => ({ ...current, notes: event.target.value }))
          }
          rows={3}
          className="rounded-xl border border-slate-300 px-4 py-2"
        />
      </label>

      <label className="flex flex-col gap-2 text-sm md:col-span-3">
        <span className="text-slate-500">Screenshots</span>
        <input
          type="file"
          accept="image/*"
          multiple
          onChange={(event) => setScreenshotFiles(Array.from(event.target.files ?? []))}
          className="rounded-xl border border-slate-300 px-4 py-2"
        />
        <span className="text-xs text-slate-500">
          Add chart screenshots, before/after captures, or markup images for this journal entry.
        </span>
        {uploadStatus && <span className="text-xs text-sea">{uploadStatus}</span>}
      </label>

      <div className="md:col-span-3">
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-white"
        >
          {isSubmitting ? 'Saving trade...' : 'Save trade'}
        </button>
      </div>
    </form>
  );
}
