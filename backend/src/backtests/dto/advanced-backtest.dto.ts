import {
  IsArray,
  IsIn,
  IsNumber,
  IsOptional,
  IsString,
  Max,
  Min,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';

class IndicatorConditionDto {
  @IsString()
  indicator!: string;

  @IsIn(['above', 'below', 'crosses_above', 'crosses_below'])
  operator!: 'above' | 'below' | 'crosses_above' | 'crosses_below';

  @IsOptional()
  value?: number | string | null;
}

export class FetchCandlesDto {
  @IsString()
  symbol!: string;

  @IsOptional()
  @IsString()
  interval?: string;

  @IsOptional()
  @IsString()
  period?: string;

  @IsOptional()
  @IsString()
  start?: string;

  @IsOptional()
  @IsString()
  end?: string;
}

export class AdvancedBacktestDto {
  @IsArray()
  candles!: Array<{
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }>;

  @IsOptional()
  @IsIn(['buy', 'sell'])
  direction?: 'buy' | 'sell';

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => IndicatorConditionDto)
  entry_conditions!: IndicatorConditionDto[];

  @IsOptional()
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => IndicatorConditionDto)
  exit_conditions?: IndicatorConditionDto[];

  @IsOptional()
  @IsNumber()
  @Min(0.1)
  @Max(10)
  stop_loss_atr_mult?: number;

  @IsOptional()
  @IsNumber()
  @Min(0.1)
  @Max(20)
  take_profit_atr_mult?: number;

  @IsOptional()
  @IsNumber()
  @Min(0.1)
  @Max(10)
  risk_per_trade?: number;

  @IsOptional()
  @IsNumber()
  @Min(1)
  @Max(100)
  forward_bars?: number;

  @IsOptional()
  @IsNumber()
  initial_balance?: number;
}
