export class UploadTradeScreenshotsResponseDto {
  urls!: string[];
}

export class ScreenshotAnalysisResponseDto {
  status!: 'none' | 'pending' | 'completed' | 'failed';
  summary!: string | null;
  detectedSetup!: string | null;
  qualityScore!: number | null;
  tags!: string[];
}
