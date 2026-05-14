import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AiModule } from './ai/ai.module';
import { AnalyticsModule } from './analytics/analytics.module';
import { BacktestsModule } from './backtests/backtests.module';
import { Strategy } from './strategies/strategy.entity';
import { StrategiesModule } from './strategies/strategies.module';
import { Trade } from './trades/trade.entity';
import { TradesModule } from './trades/trades.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRoot({
      type: 'postgres',
      host: process.env.DATABASE_HOST ?? 'localhost',
      port: Number(process.env.DATABASE_PORT ?? 5432),
      username: process.env.DATABASE_USER ?? 'postgres',
      password: process.env.DATABASE_PASSWORD ?? 'postgres',
      database: process.env.DATABASE_NAME ?? 'trading_journal',
      autoLoadEntities: true,
      synchronize: true,
    }),
    TradesModule,
    AnalyticsModule,
    AiModule,
    BacktestsModule,
    StrategiesModule,
  ],
})
export class AppModule {}
