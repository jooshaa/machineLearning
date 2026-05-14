import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  UploadedFiles,
  UseInterceptors,
} from '@nestjs/common';
import type { Request } from 'express';
import { FilesInterceptor } from '@nestjs/platform-express';
import type { File as MulterFile } from 'multer';
import { diskStorage } from 'multer';
import { extname, join } from 'path';
import { existsSync, mkdirSync } from 'fs';
import { CreateTradeDto } from './dto/create-trade.dto';
import { ImportTradesCsvDto } from './dto/import-trades-csv.dto';
import {
  ScreenshotAnalysisResponseDto,
  UploadTradeScreenshotsResponseDto,
} from './dto/upload-trade-screenshots.dto';
import { TradesService } from './trades.service';

const uploadDirectory = join(process.cwd(), 'uploads', 'trades');

if (!existsSync(uploadDirectory)) {
  mkdirSync(uploadDirectory, { recursive: true });
}

@Controller('trades')
export class TradesController {
  constructor(private readonly tradesService: TradesService) {}

  @Post()
  create(@Body() createTradeDto: CreateTradeDto) {
    return this.tradesService.create(createTradeDto);
  }

  @Get()
  findAll() {
    return this.tradesService.findAll();
  }

  @Post('import-csv')
  importCsv(@Body() importTradesCsvDto: ImportTradesCsvDto) {
    return this.tradesService.importCsv(importTradesCsvDto.csvContent);
  }

  @Post('upload-screenshots')
  @UseInterceptors(
    FilesInterceptor('files', 6, {
      storage: diskStorage({
        destination: (
          _request: Request,
          _file: MulterFile,
          callback: (error: Error | null, destination: string) => void,
        ) => callback(null, uploadDirectory),
        filename: (
          _request: Request,
          file: MulterFile,
          callback: (error: Error | null, filename: string) => void,
        ) => {
          const uniqueName = `${Date.now()}-${Math.round(Math.random() * 1e9)}${extname(
            file.originalname,
          )}`;
          callback(null, uniqueName);
        },
      }),
    }),
  )
  uploadScreenshots(
    @UploadedFiles() files: Array<{ filename: string }>,
  ): UploadTradeScreenshotsResponseDto {
    return {
      urls: files.map((file) => `/uploads/trades/${file.filename}`),
    };
  }

  @Post(':id/analyze-screenshots')
  async analyzeScreenshots(
    @Param('id') id: string,
  ): Promise<ScreenshotAnalysisResponseDto> {
    const trade = await this.tradesService.analyzeScreenshots(id);
    return {
      status: trade.screenshotAnalysisStatus,
      summary: trade.screenshotSummary,
      detectedSetup: trade.screenshotDetectedSetup,
      qualityScore: trade.screenshotQualityScore,
      tags: trade.screenshotTags ?? [],
    };
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.tradesService.remove(id);
  }
}
