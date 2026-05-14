import { Body, Controller, Get, Param, Post } from '@nestjs/common';
import { BacktestsService } from './backtests.service';
import { CreateBacktestDto } from './dto/create-backtest.dto';
import { AdvancedBacktestDto, FetchCandlesDto } from './dto/advanced-backtest.dto';

@Controller('backtests')
export class BacktestsController {
  constructor(private readonly backtestsService: BacktestsService) {}

  @Post()
  async run(@Body() createBacktestDto: CreateBacktestDto) {
    return this.backtestsService.runBacktest(createBacktestDto);
  }

  @Post('fetch-candles')
  async fetchCandles(@Body() dto: FetchCandlesDto) {
    return this.backtestsService.fetchCandles(dto);
  }

  @Post('advanced')
  async runAdvanced(@Body() dto: AdvancedBacktestDto) {
    return this.backtestsService.runAdvancedBacktest(dto);
  }

  @Post('fabio')
  async runFabio(@Body() dto: Record<string, unknown>) {
    return this.backtestsService.runFabioBacktest(dto);
  }

  @Post('fabio/l3')
  async runFabioL3(@Body() dto: Record<string, unknown>) {
    return this.backtestsService.runFabioL3Backtest(dto);
  }

  @Post('fabio/l3/start')
  async startFabioL3(@Body() dto: Record<string, unknown>) {
    return this.backtestsService.startFabioL3Backtest(dto);
  }

  @Get('fabio/l3/analysis')
  async getFabioL3Analysis() {
    return this.backtestsService.getFabioL3Analysis();
  }

  @Get('fabio/l3/status/:id')
  async getFabioL3Status(@Param('id') id: string) {
    return this.backtestsService.getFabioL3Status(id);
  }

  @Get('fabio/l3/result/:id')
  async getFabioL3Result(@Param('id') id: string) {
    return this.backtestsService.getFabioL3Result(id);
  }

  @Post('fabio/l3/cancel/:id')
  async cancelFabioL3(@Param('id') id: string) {
    return this.backtestsService.cancelFabioL3(id);
  }

  @Post('fabio/train')
  async trainFabio(@Body() dto: Record<string, unknown>) {
    return this.backtestsService.trainFabioModel(dto);
  }

  @Post('fabio/save')
  async saveFabio(@Body() dto: any) {
    return this.backtestsService.saveFabioResult(dto);
  }

  @Post('fabio/history')
  async getFabioHistory() {
    return this.backtestsService.getFabioHistory();
  }

  @Get('fabio/memory')
  async getFabioMemory() {
    return this.backtestsService.getFabioAiMemory();
  }

  @Get('candles/local/:date')
  async getLocalCandles(@Param('date') date: string) {
    return this.backtestsService.getLocalCandles(date);
  }
}
