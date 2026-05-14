import { Controller, Get } from '@nestjs/common';
import { AiService } from './ai.service';

@Controller('ai-analysis')
export class AiController {
  constructor(private readonly aiService: AiService) {}

  @Get()
  analyzeLatestTrade() {
    return this.aiService.analyzeLatestTrade();
  }
}

