import { IsString, MinLength } from 'class-validator';

export class ImportTradesCsvDto {
  @IsString()
  @MinLength(10)
  csvContent!: string;
}
