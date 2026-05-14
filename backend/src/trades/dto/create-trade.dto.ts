import {
  IsIn,
  IsNumber,
  IsOptional,
  IsArray,
  IsPositive,
  IsString,
  Length,
  Max,
  Min,
} from 'class-validator';

export class CreateTradeDto {
  @IsString()
  @Length(3, 20)
  pair!: string;

  @IsOptional()
  @IsString()
  @Length(1, 40)
  strategyVersion?: string;

  @IsOptional()
  @IsIn(['M5', 'M15', 'H1', 'H4', 'D1'])
  timeframe?: 'M5' | 'M15' | 'H1' | 'H4' | 'D1';

  @IsIn(['London', 'NY', 'Asia'])
  session!: 'London' | 'NY' | 'Asia';

  @IsIn(['breakout', 'pullback', 'reversal'])
  setup!: 'breakout' | 'pullback' | 'reversal';

  @IsIn(['buy', 'sell'])
  direction!: 'buy' | 'sell';

  @IsNumber()
  @IsPositive()
  entryPrice!: number;

  @IsNumber()
  @IsPositive()
  stopLoss!: number;

  @IsNumber()
  @IsPositive()
  takeProfit!: number;

  @IsNumber()
  @Min(0)
  riskReward!: number;

  @IsIn(['win', 'loss'])
  result!: 'win' | 'loss';

  @IsNumber()
  @Min(1)
  @Max(5)
  confidence!: number;

  @IsNumber()
  @Min(1)
  @Max(5)
  confluence!: number;

  @IsOptional()
  @IsIn(['calm', 'confident', 'hesitant', 'fearful', 'revenge', 'neutral'])
  emotion?: 'calm' | 'confident' | 'hesitant' | 'fearful' | 'revenge' | 'neutral';

  @IsOptional()
  @IsString()
  @Length(0, 120)
  mistake?: string;

  @IsOptional()
  @IsString()
  @Length(0, 1000)
  notes?: string;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  screenshotUrls?: string[];

  @IsNumber()
  profit!: number;
}
