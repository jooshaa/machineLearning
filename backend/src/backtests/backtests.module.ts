import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BacktestsController } from './backtests.controller';
import { BacktestsService } from './backtests.service';
import { StrategiesModule } from '../strategies/strategies.module';
import { FabioBacktestResult } from './fabio-result.entity';

@Module({
  imports: [StrategiesModule, TypeOrmModule.forFeature([FabioBacktestResult])],
  controllers: [BacktestsController],
  providers: [BacktestsService],
})
export class BacktestsModule {}
