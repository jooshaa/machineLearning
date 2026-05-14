import {
  IsArray,
  IsBoolean,
  IsIn,
  IsNumber,
  IsOptional,
  IsString,
  Length,
  Max,
  Min,
} from 'class-validator';

export class CreateStrategyDto {
  @IsString()
  @Length(2, 80)
  name!: string;

  @IsString()
  @Length(1, 40)
  version!: string;

  @IsString()
  @Length(3, 20)
  pair!: string;

  @IsIn(['breakout', 'pullback', 'reversal'])
  setup!: 'breakout' | 'pullback' | 'reversal';

  @IsIn(['buy', 'sell'])
  direction!: 'buy' | 'sell';

  @IsIn(['M5', 'M15', 'H1', 'H4', 'D1'])
  timeframe!: 'M5' | 'M15' | 'H1' | 'H4' | 'D1';

  @IsNumber()
  @Min(0.1)
  @Max(10)
  riskReward!: number;

  @IsNumber()
  @Min(2)
  @Max(200)
  lookback!: number;

  @IsNumber()
  @Min(1)
  @Max(50)
  forwardBars!: number;

  @IsNumber()
  @Min(0.01)
  @Max(5)
  riskPercent!: number;

  @IsOptional()
  @IsBoolean()
  active?: boolean;

  @IsOptional()
  @IsString()
  @Length(0, 1000)
  description?: string;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  tags?: string[];
}

