import { BadRequestException, Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { readFile } from 'fs/promises';
import { join, basename } from 'path';
import { Repository } from 'typeorm';
import { parseCsv } from '../common/csv';
import { CreateTradeDto } from './dto/create-trade.dto';
import { Trade } from './trade.entity';

@Injectable()
export class TradesService {
  constructor(
    @InjectRepository(Trade)
    private readonly tradesRepository: Repository<Trade>,
  ) {}

  async create(createTradeDto: CreateTradeDto) {
    const trade = this.tradesRepository.create(createTradeDto);
    const savedTrade = await this.tradesRepository.save(trade);

    if (savedTrade.screenshotUrls?.length && process.env.OPENAI_API_KEY) {
      void this.analyzeScreenshots(savedTrade.id);
    }

    return savedTrade;
  }

  async findAll() {
    return this.tradesRepository.find({
      order: {
        createdAt: 'DESC',
      },
    });
  }

  async findLatest() {
    return this.tradesRepository.findOne({
      order: {
        createdAt: 'DESC',
      },
    });
  }

  async remove(id: string) {
    await this.tradesRepository.delete(id);
    return { success: true };
  }

  async importCsv(csvContent: string) {
    const rows = parseCsv(csvContent);

    if (rows.length === 0) {
      throw new BadRequestException('CSV is empty or missing a header row.');
    }

    const trades = rows.map((row) => this.mapCsvRow(row));
    const entities = this.tradesRepository.create(trades);
    const saved = await this.tradesRepository.save(entities);

    return {
      imported: saved.length,
      sample: saved.slice(0, 3),
    };
  }

  async analyzeScreenshots(id: string) {
    const trade = await this.tradesRepository.findOneBy({ id });

    if (!trade) {
      throw new BadRequestException('Trade not found.');
    }

    if (!trade.screenshotUrls?.length) {
      return this.tradesRepository.save({
        ...trade,
        screenshotAnalysisStatus: 'none',
        screenshotSummary: null,
        screenshotDetectedSetup: null,
        screenshotQualityScore: null,
        screenshotTags: [],
      });
    }

    if (!process.env.OPENAI_API_KEY) {
      throw new BadRequestException('OPENAI_API_KEY is required for screenshot analysis.');
    }

    await this.tradesRepository.save({
      ...trade,
      screenshotAnalysisStatus: 'pending',
    });

    try {
      const analysis = await analyzeTradeScreenshotsWithOpenAI(trade);
      return this.tradesRepository.save({
        ...trade,
        screenshotAnalysisStatus: 'completed',
        screenshotSummary: analysis.summary,
        screenshotDetectedSetup: analysis.detectedSetup,
        screenshotQualityScore: analysis.qualityScore,
        screenshotTags: analysis.tags,
      });
    } catch {
      return this.tradesRepository.save({
        ...trade,
        screenshotAnalysisStatus: 'failed',
      });
    }
  }

  private mapCsvRow(row: Record<string, string>): CreateTradeDto {
    const pair = getValue(row, ['pair', 'symbol', 'ticker', 'instrument']);
    if (!pair) {
      throw new BadRequestException('Each row must include a pair or symbol column.');
    }

    const direction = normalizeDirection(
      getValue(row, ['direction', 'side', 'trade_type']) ?? 'buy',
    );
    const entryPrice = parseNumber(getValue(row, ['entry_price', 'entry', 'entryprice']));
    const stopLoss = parseNumber(getValue(row, ['stop_loss', 'sl', 'stoploss'])) ?? 0.0001;
    const takeProfit =
      parseNumber(getValue(row, ['take_profit', 'tp', 'takeprofit'])) ?? entryPrice ?? 0.0002;
    const profit = parseNumber(getValue(row, ['profit', 'pnl', 'net_profit'])) ?? 0;
    const result = normalizeResult(getValue(row, ['result', 'outcome']), profit);
    const riskReward =
      parseNumber(getValue(row, ['risk_reward', 'rr', 'rrr'])) ??
      inferRiskReward(entryPrice, stopLoss, takeProfit);

    return {
      pair,
      strategyVersion: getValue(row, ['strategy_version', 'version', 'strategy_id']) ?? 'v1',
      timeframe:
        normalizeTimeframe(getValue(row, ['timeframe', 'tf', 'interval'])) ?? 'M15',
      session:
        normalizeSession(getValue(row, ['session', 'market_session'])) ?? 'NY',
      setup: normalizeSetup(getValue(row, ['setup', 'strategy', 'pattern'])) ?? 'breakout',
      direction,
      entryPrice: entryPrice ?? 1,
      stopLoss,
      takeProfit,
      riskReward,
      result,
      confidence: clampInteger(parseNumber(getValue(row, ['confidence', 'conviction'])) ?? 3),
      confluence: clampInteger(parseNumber(getValue(row, ['confluence', 'confluences'])) ?? 1),
      emotion:
        normalizeEmotion(getValue(row, ['emotion', 'psychology', 'feeling'])) ?? 'neutral',
      mistake: getValue(row, ['mistake', 'error', 'mistake_tag']) ?? '',
      notes: getValue(row, ['notes', 'comment', 'description']) ?? '',
      screenshotUrls: parseScreenshotUrls(
        getValue(row, ['screenshot_urls', 'screenshots', 'images', 'image']),
      ),
      profit,
    };
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

function normalizeDirection(value: string) {
  return value.toLowerCase().includes('sell') || value.toLowerCase().includes('short')
    ? 'sell'
    : 'buy';
}

function normalizeResult(value: string | null, profit: number) {
  if (value) {
    return value.toLowerCase().includes('loss') ? 'loss' : 'win';
  }

  return profit >= 0 ? 'win' : 'loss';
}

function normalizeSession(value: string | null) {
  if (!value) {
    return null;
  }
  const lower = value.toLowerCase();
  if (lower.includes('london')) {
    return 'London';
  }
  if (lower.includes('asia')) {
    return 'Asia';
  }
  if (lower.includes('ny') || lower.includes('new york')) {
    return 'NY';
  }
  return null;
}

function normalizeSetup(value: string | null) {
  if (!value) {
    return null;
  }
  const lower = value.toLowerCase();
  if (lower.includes('pull')) {
    return 'pullback';
  }
  if (lower.includes('reversal')) {
    return 'reversal';
  }
  if (lower.includes('break')) {
    return 'breakout';
  }
  return null;
}

function normalizeTimeframe(value: string | null) {
  if (!value) {
    return null;
  }
  const upper = value.toUpperCase();
  if (['M5', 'M15', 'H1', 'H4', 'D1'].includes(upper)) {
    return upper as 'M5' | 'M15' | 'H1' | 'H4' | 'D1';
  }
  return null;
}

function normalizeEmotion(value: string | null) {
  if (!value) {
    return null;
  }
  const lower = value.toLowerCase();
  if (['calm', 'confident', 'hesitant', 'fearful', 'revenge', 'neutral'].includes(lower)) {
    return lower as 'calm' | 'confident' | 'hesitant' | 'fearful' | 'revenge' | 'neutral';
  }
  return null;
}

function inferRiskReward(
  entryPrice: number | null,
  stopLoss: number | null,
  takeProfit: number | null,
) {
  if (!entryPrice || !stopLoss || !takeProfit) {
    return 2;
  }

  const risk = Math.abs(entryPrice - stopLoss);
  const reward = Math.abs(takeProfit - entryPrice);

  if (risk === 0) {
    return 2;
  }

  return Number((reward / risk).toFixed(2));
}

function clampInteger(value: number) {
  return Math.max(1, Math.min(5, Math.round(value)));
}

function parseScreenshotUrls(value: string | null) {
  if (!value) {
    return [];
  }

  return value
    .split(/[|,;]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => (item.startsWith('/uploads/') ? item : `/uploads/trades/${basename(item)}`));
}

async function analyzeTradeScreenshotsWithOpenAI(trade: Trade) {
  const images = await Promise.all(
    (trade.screenshotUrls ?? []).slice(0, 3).map(async (url) => {
      const filename = basename(url);
      const filePath = join(process.cwd(), 'uploads', 'trades', filename);
      const buffer = await readFile(filePath);
      const extension = filename.split('.').pop()?.toLowerCase() ?? 'png';
      const mimeType =
        extension === 'jpg' || extension === 'jpeg'
          ? 'image/jpeg'
          : extension === 'webp'
            ? 'image/webp'
            : 'image/png';

      return `data:${mimeType};base64,${buffer.toString('base64')}`;
    }),
  );

  const response = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: process.env.OPENAI_VISION_MODEL ?? 'gpt-5',
      input: [
        {
          role: 'developer',
          content: [
            {
              type: 'input_text',
              text:
                'Analyze trading chart screenshots for journaling. Return only JSON with keys summary, detectedSetup, qualityScore, tags. qualityScore must be 1 to 5. detectedSetup should be breakout, pullback, reversal, or unclear. tags should be short strings describing market structure or execution context.',
            },
          ],
        },
        {
          role: 'user',
          content: [
            {
              type: 'input_text',
              text: `Trade context: pair=${trade.pair}, strategyVersion=${trade.strategyVersion}, timeframe=${trade.timeframe ?? 'unknown'}, session=${trade.session}, setup=${trade.setup}, direction=${trade.direction}, notes=${trade.notes ?? ''}`,
            },
            ...images.map((imageUrl) => ({
              type: 'input_image' as const,
              image_url: imageUrl,
              detail: 'high' as const,
            })),
          ],
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error('OpenAI screenshot analysis failed');
  }

  const payload = (await response.json()) as {
    output?: Array<{ content?: Array<{ type?: string; text?: string }> }>;
  };
  const text = payload.output
    ?.flatMap((item) => item.content ?? [])
    .find((item) => item.type === 'output_text')?.text;

  if (!text) {
    throw new Error('Screenshot analysis returned no text payload');
  }

  const parsed = JSON.parse(text) as {
    summary?: string;
    detectedSetup?: string;
    qualityScore?: number;
    tags?: string[];
  };

  return {
    summary: parsed.summary ?? null,
    detectedSetup: parsed.detectedSetup ?? null,
    qualityScore:
      typeof parsed.qualityScore === 'number'
        ? Math.max(1, Math.min(5, Math.round(parsed.qualityScore)))
        : null,
    tags: Array.isArray(parsed.tags) ? parsed.tags.slice(0, 8) : [],
  };
}
