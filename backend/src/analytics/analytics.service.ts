import { Injectable } from '@nestjs/common';
import { calculateAnalytics } from '../common/trade-metrics';
import { TradesService } from '../trades/trades.service';

@Injectable()
export class AnalyticsService {
  constructor(private readonly tradesService: TradesService) {}

  async getSummary() {
    const trades = await this.tradesService.findAll();
    return calculateAnalytics(trades);
  }
}

