import { BadRequestException, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { parseCsv } from '../common/csv';
import { StrategiesService } from '../strategies/strategies.service';
import { CreateBacktestDto } from './dto/create-backtest.dto';
import { AdvancedBacktestDto, FetchCandlesDto } from './dto/advanced-backtest.dto';
import { FabioBacktestResult } from './fabio-result.entity';

export interface SimulatedTrade {
  timestamp: string;
  entry: number;
  stopLoss: number;
  takeProfit: number;
  result: 'win' | 'loss';
  pnlR: number;
}

export interface BacktestResult {
  strategyId: string | null;
  strategyVersion: string | null;
  strategyName: string | null;
  pair: string;
  setup: string;
  direction: string;
  timeframe: string | null;
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  expectancyR: number;
  totalR: number;
  maxDrawdownR: number;
  equityCurve: Array<{ index: number; equity: number }>;
  sampleTrades: SimulatedTrade[];
  notes: string[];
}

interface CandleInput {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

@Injectable()
export class BacktestsService {
  private readonly mlServiceUrl: string;

  constructor(
    private readonly strategiesService: StrategiesService,
    private readonly configService: ConfigService,
    @InjectRepository(FabioBacktestResult)
    private readonly fabioRepo: Repository<FabioBacktestResult>,
  ) {
    this.mlServiceUrl = this.configService.get<string>('ML_SERVICE_URL') ?? 'http://localhost:8000';
  }

  async runBacktest(dto: CreateBacktestDto): Promise<BacktestResult> {
    const strategy = dto.strategyId
      ? await this.strategiesService.findOne(dto.strategyId)
      : null;
    const resolved = strategy
      ? {
          ...dto,
          pair: strategy.pair,
          setup: strategy.setup,
          direction: strategy.direction,
          timeframe: strategy.timeframe,
          riskReward: Number(strategy.riskReward),
          lookback: strategy.lookback,
        }
      : dto;

    const candles = this.resolveCandles(resolved);
    const trades = this.simulate(
      {
        ...resolved,
        forwardBars: strategy?.forwardBars ?? 7,
        riskPercent: Number(strategy?.riskPercent ?? 0.2),
      },
      candles,
    );
    const wins = trades.filter((trade) => trade.result === 'win');
    const totalR = trades.reduce((sum, trade) => sum + trade.pnlR, 0);
    const equityCurve = trades.map((trade, index) => ({
      index: index + 1,
      equity: trades.slice(0, index + 1).reduce((sum, current) => sum + current.pnlR, 0),
    }));

    return {
      strategyId: strategy?.id ?? null,
      strategyVersion: strategy?.version ?? null,
      strategyName: strategy?.name ?? null,
      pair: resolved.pair,
      setup: resolved.setup,
      direction: resolved.direction,
      timeframe: resolved.timeframe ?? null,
      trades: trades.length,
      wins: wins.length,
      losses: trades.length - wins.length,
      winRate: trades.length > 0 ? (wins.length / trades.length) * 100 : 0,
      expectancyR: trades.length > 0 ? totalR / trades.length : 0,
      totalR,
      maxDrawdownR: this.calculateDrawdown(equityCurve),
      equityCurve,
      sampleTrades: trades.slice(0, 8),
      notes: this.buildNotes(resolved, trades, strategy?.name ?? null),
    };
  }

  private simulate(
    dto: CreateBacktestDto & { forwardBars: number; riskPercent: number },
    candles: CandleInput[],
  ): SimulatedTrade[] {
    const trades: SimulatedTrade[] = [];

    for (let index = dto.lookback; index < candles.length - 1; index += 1) {
      const window = candles.slice(index - dto.lookback, index);
      const candle = candles[index];
      const previousHigh = Math.max(...window.map((item) => item.high));
      const previousLow = Math.min(...window.map((item) => item.low));
      const range = Math.max(previousHigh - previousLow, 0.0001);

      const shouldEnter =
        dto.setup === 'breakout'
          ? dto.direction === 'buy'
            ? candle.close > previousHigh
            : candle.close < previousLow
          : dto.setup === 'pullback'
            ? dto.direction === 'buy'
              ? candle.low <= previousHigh &&
                candle.close > window[window.length - 1].close
              : candle.high >= previousLow &&
                candle.close < window[window.length - 1].close
            : dto.direction === 'buy'
              ? candle.low <= Math.min(...window.map((item) => item.low))
              : candle.high >= Math.max(...window.map((item) => item.high));

      if (!shouldEnter) {
        continue;
      }

      const entry = candle.close;
      const risk = Math.max(range * dto.riskPercent, Math.abs(entry * 0.0025));
      const stopLoss = dto.direction === 'buy' ? entry - risk : entry + risk;
      const takeProfit =
        dto.direction === 'buy'
          ? entry + risk * dto.riskReward
          : entry - risk * dto.riskReward;
      const forwardCandles = candles.slice(index + 1, index + 1 + dto.forwardBars);

      let result: 'win' | 'loss' = 'loss';
      for (const forward of forwardCandles) {
        if (dto.direction === 'buy') {
          if (forward.low <= stopLoss) {
            result = 'loss';
            break;
          }
          if (forward.high >= takeProfit) {
            result = 'win';
            break;
          }
        } else {
          if (forward.high >= stopLoss) {
            result = 'loss';
            break;
          }
          if (forward.low <= takeProfit) {
            result = 'win';
            break;
          }
        }
      }

      trades.push({
        timestamp: candle.timestamp,
        entry,
        stopLoss,
        takeProfit,
        result,
        pnlR: result === 'win' ? dto.riskReward : -1,
      });
    }

    return trades;
  }

  private resolveCandles(dto: CreateBacktestDto): CandleInput[] {
    if (dto.candles && dto.candles.length > 0) {
      return dto.candles;
    }

    if (!dto.csvContent) {
      throw new BadRequestException('Provide either candles JSON or csvContent.');
    }

    const rows = parseCsv(dto.csvContent);
    const candles = rows
      .map((row) => ({
        timestamp: getValue(row, ['timestamp', 'time', 'date']) ?? '',
        open: parseNumber(getValue(row, ['open'])) ?? NaN,
        high: parseNumber(getValue(row, ['high'])) ?? NaN,
        low: parseNumber(getValue(row, ['low'])) ?? NaN,
        close: parseNumber(getValue(row, ['close'])) ?? NaN,
      }))
      .filter(
        (candle) =>
          candle.timestamp &&
          Number.isFinite(candle.open) &&
          Number.isFinite(candle.high) &&
          Number.isFinite(candle.low) &&
          Number.isFinite(candle.close),
      );

    if (candles.length < 10) {
      throw new BadRequestException('CSV candle import needs at least 10 valid OHLC rows.');
    }

    return candles;
  }

  private calculateDrawdown(points: Array<{ index: number; equity: number }>) {
    let peak = 0;
    let drawdown = 0;

    for (const point of points) {
      peak = Math.max(peak, point.equity);
      drawdown = Math.max(drawdown, peak - point.equity);
    }

    return drawdown;
  }

  private buildNotes(dto: CreateBacktestDto, trades: SimulatedTrade[], strategyName: string | null) {
    if (trades.length === 0) {
      return ['No qualifying setups were found for the selected rules and candle sample.'];
    }

    const wins = trades.filter((trade) => trade.result === 'win').length;
    const winRate = (wins / trades.length) * 100;
    const notes = [
      strategyName ? `Strategy: ${strategyName}.` : 'Ad-hoc strategy run.',
      `${dto.setup} ${dto.direction} logic found ${trades.length} candidate trades.`,
      `Observed win rate is ${winRate.toFixed(1)}% across the uploaded candle slice.`,
    ];

    if (winRate < 40) {
      notes.push('This rule set is currently fragile and likely needs tighter filters or better context.');
    } else if (winRate > 55) {
      notes.push('This rule set shows promise and is worth comparing against your discretionary journal entries.');
    }

    return notes;
  }

  async fetchCandles(dto: FetchCandlesDto) {
    const response = await fetch(`${this.mlServiceUrl}/fetch-candles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dto),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'ML service unreachable' }));
      throw new BadRequestException(error.detail ?? 'Failed to fetch candles');
    }

    return response.json();
  }

  async runAdvancedBacktest(dto: AdvancedBacktestDto) {
    const response = await fetch(`${this.mlServiceUrl}/backtest-advanced`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dto),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'ML service unreachable' }));
      throw new BadRequestException(error.detail ?? 'Advanced backtest failed');
    }

    return response.json();
  }

  async runFabioBacktest(dto: Record<string, unknown>) {
    const response = await fetch(`${this.mlServiceUrl}/backtest-fabio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dto),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'ML service unreachable' }));
      throw new BadRequestException(error.detail ?? 'Fabio backtest failed');
    }

    return response.json();
  }

  async runFabioL3Backtest(dto: Record<string, unknown>) {
    const response = await fetch(`${this.mlServiceUrl}/backtest-l3`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dto),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'ML service unreachable' }));
      throw new BadRequestException(error.detail ?? 'Fabio L3 backtest failed');
    }

    return response.json();
  }

  async startFabioL3Backtest(dto: Record<string, unknown>) {
    const response = await fetch(`${this.mlServiceUrl}/backtest-l3/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dto),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'ML service unreachable' }));
      throw new BadRequestException(error.detail ?? 'Failed to start L3 backtest');
    }
    return response.json();
  }

  async getFabioL3Status(id: string) {
    const response = await fetch(`${this.mlServiceUrl}/backtest-l3/status/${id}`);
    if (!response.ok) return { status: 'error', error: 'Service error' };
    return response.json();
  }

  async getFabioL3Analysis() {
    const response = await fetch(`${this.mlServiceUrl}/backtest-l3/analysis`);
    if (!response.ok) return response.json(); 
    return response.json();
  }

  async getFabioL3Result(id: string) {
    const response = await fetch(`${this.mlServiceUrl}/backtest-l3/result/${id}`);
    if (!response.ok) return { error: 'Result not ready or missing' };
    return response.json();
  }

  async cancelFabioL3(id: string) {
    const response = await fetch(`${this.mlServiceUrl}/backtest-l3/cancel/${id}`, { method: 'POST' });
    return response.json();
  }

  async trainFabioModel(dto: Record<string, unknown>) {
    const response = await fetch(`${this.mlServiceUrl}/train-fabio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dto),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'ML training failed' }));
      throw new BadRequestException(error.detail ?? 'Training failed');
    }

    return response.json();
  }

  async saveFabioResult(dto: any) {
    const result = this.fabioRepo.create({
      symbol: dto.symbol,
      timeframe: dto.timeframe,
      period: dto.period,
      session_filter: dto.session_filter || 'all',
      total_trades: dto.result.total_trades,
      win_rate: dto.result.win_rate,
      total_r: dto.result.total_r,
      profit_factor: dto.result.profit_factor,
      expectancy_r: dto.result.expectancy_r,
      sharpe_ratio: dto.result.sharpe_ratio,
      max_drawdown_r: dto.result.max_drawdown_r,
      return_pct: dto.result.return_pct,
      full_result: dto.result,
      params: dto.params,
      notes: dto.notes || '',
    });
    return this.fabioRepo.save(result);
  }

  async getFabioHistory() {
    return this.fabioRepo.find({
      order: { created_at: 'DESC' },
      take: 20,
    });
  }

  async getFabioAiMemory() {
    const response = await fetch(`${this.mlServiceUrl}/fabio-ai-memory`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new BadRequestException('Failed to fetch AI memory');
    }

    return response.json();
  }

  async getLocalCandles(date: string, symbol = 'NQ') {
    const mlUrl = this.configService.get<string>('ML_SERVICE_URL') ?? 'http://localhost:8000';
    const response = await fetch(`${mlUrl}/candles/local/${date}?symbol=${symbol}`, {
      method: 'GET',
    });

    if (!response.ok) {
      return { candles: [] };
    }

    return response.json();
  }
}

function getValue(row: Record<string, string>, keys: string[]) {
  for (const key of keys) {
    const value = row[key];
    if (value !== undefined && value !== '') {
      return value;
    }
  }
  return null;
}

function parseNumber(value: string | null) {
  if (!value) {
    return null;
  }

  const parsed = Number(value.replace(/[^0-9.-]/g, ''));
  return Number.isFinite(parsed) ? parsed : null;
}

// ---------------------------------------------------------------------------
// Advanced backtest methods (proxy to ML service)
// ---------------------------------------------------------------------------

// These are defined as a module-augmentation style addition to the class above.
// We use declaration merging via prototype assignment for cleanliness.
