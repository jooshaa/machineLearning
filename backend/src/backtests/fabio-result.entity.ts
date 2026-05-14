import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity({ name: 'fabio_backtest_results' })
export class FabioBacktestResult {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'varchar', length: 20 })
  symbol!: string;

  @Column({ type: 'varchar', length: 10 })
  timeframe!: string;

  @Column({ type: 'varchar', length: 20 })
  period!: string;

  @Column({ type: 'varchar', length: 20, default: 'all' })
  session_filter!: string;

  // Core stats
  @Column({ type: 'int' })
  total_trades!: number;

  @Column({ type: 'decimal', precision: 6, scale: 2 })
  win_rate!: number;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  total_r!: number;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  profit_factor!: number;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  expectancy_r!: number;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  sharpe_ratio!: number;

  @Column({ type: 'decimal', precision: 10, scale: 4 })
  max_drawdown_r!: number;

  @Column({ type: 'decimal', precision: 10, scale: 2 })
  return_pct!: number;

  // Full result JSON (trades, equity curve, breakdowns etc.)
  @Column({ type: 'jsonb' })
  full_result!: Record<string, unknown>;

  // Parameters used
  @Column({ type: 'jsonb' })
  params!: Record<string, unknown>;

  @Column({ type: 'text', nullable: true })
  notes!: string | null;

  @CreateDateColumn({ name: 'created_at' })
  created_at!: Date;
}
