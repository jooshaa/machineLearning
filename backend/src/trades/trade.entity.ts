import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

export type TradeSession = 'London' | 'NY' | 'Asia';
export type TradeSetup = 'breakout' | 'pullback' | 'reversal';
export type TradeDirection = 'buy' | 'sell';
export type TradeResult = 'win' | 'loss';
export type TradeTimeframe = 'M5' | 'M15' | 'H1' | 'H4' | 'D1';
export type TradeEmotion =
  | 'calm'
  | 'confident'
  | 'hesitant'
  | 'fearful'
  | 'revenge'
  | 'neutral';
export type ScreenshotAnalysisStatus = 'none' | 'pending' | 'completed' | 'failed';

const decimalTransformer = {
  to: (value: number) => value,
  from: (value: string | number) => Number(value),
};

@Entity({ name: 'trades' })
export class Trade {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'varchar', length: 20 })
  pair!: string;

  @Column({ name: 'strategy_version', type: 'varchar', length: 40, default: 'v1' })
  strategyVersion!: string;

  @Column({ type: 'varchar', length: 10, nullable: true })
  timeframe!: TradeTimeframe | null;

  @Column({ type: 'varchar', length: 20 })
  session!: TradeSession;

  @Column({ type: 'varchar', length: 20 })
  setup!: TradeSetup;

  @Column({ type: 'varchar', length: 10 })
  direction!: TradeDirection;

  @Column({
    name: 'entry_price',
    type: 'decimal',
    precision: 14,
    scale: 6,
    transformer: decimalTransformer,
  })
  entryPrice!: number;

  @Column({
    name: 'stop_loss',
    type: 'decimal',
    precision: 14,
    scale: 6,
    transformer: decimalTransformer,
  })
  stopLoss!: number;

  @Column({
    name: 'take_profit',
    type: 'decimal',
    precision: 14,
    scale: 6,
    transformer: decimalTransformer,
  })
  takeProfit!: number;

  @Column({
    name: 'risk_reward',
    type: 'decimal',
    precision: 10,
    scale: 2,
    transformer: decimalTransformer,
  })
  riskReward!: number;

  @Column({ type: 'varchar', length: 10 })
  result!: TradeResult;

  @Column({ type: 'int', default: 3 })
  confidence!: number;

  @Column({ type: 'int', default: 1 })
  confluence!: number;

  @Column({ type: 'varchar', length: 20, nullable: true })
  emotion!: TradeEmotion | null;

  @Column({ type: 'varchar', length: 120, nullable: true })
  mistake!: string | null;

  @Column({ type: 'text', nullable: true })
  notes!: string | null;

  @Column({ name: 'screenshot_urls', type: 'simple-json', nullable: true })
  screenshotUrls!: string[] | null;

  @Column({
    name: 'screenshot_analysis_status',
    type: 'varchar',
    length: 20,
    default: 'none',
  })
  screenshotAnalysisStatus!: ScreenshotAnalysisStatus;

  @Column({ name: 'screenshot_summary', type: 'text', nullable: true })
  screenshotSummary!: string | null;

  @Column({ name: 'screenshot_detected_setup', type: 'varchar', length: 40, nullable: true })
  screenshotDetectedSetup!: string | null;

  @Column({ name: 'screenshot_quality_score', type: 'int', nullable: true })
  screenshotQualityScore!: number | null;

  @Column({ name: 'screenshot_tags', type: 'simple-json', nullable: true })
  screenshotTags!: string[] | null;

  @Column({
    type: 'decimal',
    precision: 12,
    scale: 2,
    transformer: decimalTransformer,
  })
  profit!: number;

  @CreateDateColumn({ name: 'created_at' })
  createdAt!: Date;
}
