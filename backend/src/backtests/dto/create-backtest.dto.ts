import {
  ArrayMinSize,
  IsArray,
  IsIn,
  IsNumber,
  IsOptional,
  IsString,
  Max,
  Min,
  MinLength,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';

class CandleDto {
  @IsString()
  timestamp!: string;

  @IsNumber()
  open!: number;

  @IsNumber()
  high!: number;

  @IsNumber()
  low!: number;

  @IsNumber()
  close!: number;
}

export class CreateBacktestDto {
  @IsOptional()
  @IsString()
  strategyId?: string;

  @IsString()
  pair!: string;

  @IsIn(['breakout', 'pullback', 'reversal'])
  setup!: 'breakout' | 'pullback' | 'reversal';

  @IsIn(['buy', 'sell'])
  direction!: 'buy' | 'sell';

  @IsOptional()
  @IsIn(['M5', 'M15', 'H1', 'H4', 'D1'])
  timeframe?: 'M5' | 'M15' | 'H1' | 'H4' | 'D1';

  @IsNumber()
  @Min(0.1)
  @Max(10)
  riskReward!: number;

  @IsNumber()
  @Min(2)
  @Max(100)
  lookback!: number;

  @IsOptional()
  @IsArray()
  @ArrayMinSize(10)
  @ValidateNested({ each: true })
  @Type(() => CandleDto)
  candles?: CandleDto[];

  @IsOptional()
  @IsString()
  @MinLength(10)
  csvContent?: string;
}
