import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { TradesModule } from '../trades/trades.module';
import { AiController } from './ai.controller';
import { AiService } from './ai.service';

@Module({
  imports: [TradesModule, HttpModule],
  controllers: [AiController],
  providers: [AiService],
})
export class AiModule {}

