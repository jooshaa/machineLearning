import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

export type StrategySetup = 'breakout' | 'pullback' | 'reversal';
export type StrategyDirection = 'buy' | 'sell';
export type StrategyTimeframe = 'M5' | 'M15' | 'H1' | 'H4' | 'D1';

@Entity({ name: 'strategies' })
export class Strategy {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'varchar', length: 80 })
  name!: string;

  @Column({ type: 'varchar', length: 40 })
  version!: string;

  @Column({ type: 'varchar', length: 20 })
  pair!: string;

  @Column({ type: 'varchar', length: 20 })
  setup!: StrategySetup;

  @Column({ type: 'varchar', length: 10 })
  direction!: StrategyDirection;

  @Column({ type: 'varchar', length: 10 })
  timeframe!: StrategyTimeframe;

  @Column({ type: 'decimal', precision: 10, scale: 2, default: 2 })
  riskReward!: number;

  @Column({ type: 'int', default: 20 })
  lookback!: number;

  @Column({ type: 'int', default: 7 })
  forwardBars!: number;

  @Column({ type: 'decimal', precision: 10, scale: 4, default: 0.2 })
  riskPercent!: number;

  @Column({ type: 'boolean', default: true })
  active!: boolean;

  @Column({ type: 'text', nullable: true })
  description!: string | null;

  @Column({ type: 'simple-json', nullable: true })
  tags!: string[] | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt!: Date;
}

