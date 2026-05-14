import { BadGatewayException, HttpException, Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { TradesService } from '../trades/trades.service';

@Injectable()
export class AiService {
  constructor(
    private readonly tradesService: TradesService,
    private readonly httpService: HttpService,
  ) {}

  async analyzeLatestTrade() {
    const [trades, latestTrade] = await Promise.all([
      this.tradesService.findAll(),
      this.tradesService.findLatest(),
    ]);

    if (!latestTrade || trades.length < 5) {
      throw new HttpException(
        'At least 5 trades are required for AI analysis.',
        400,
      );
    }

    const mlServiceUrl = process.env.ML_SERVICE_URL ?? 'http://localhost:8000';

    try {
      const response = await firstValueFrom(
        this.httpService.post(`${mlServiceUrl}/predict`, {
          trades,
          trade: latestTrade,
        }),
      );

      return response.data;
    } catch {
      throw new BadGatewayException(
        'ML service is unavailable or returned an invalid response.',
      );
    }
  }
}
