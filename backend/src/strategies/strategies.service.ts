import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { CreateStrategyDto } from './dto/create-strategy.dto';
import { Strategy } from './strategy.entity';

@Injectable()
export class StrategiesService {
  constructor(
    @InjectRepository(Strategy)
    private readonly strategiesRepository: Repository<Strategy>,
  ) {}

  async create(createStrategyDto: CreateStrategyDto) {
    const strategy = this.strategiesRepository.create({
      active: true,
      tags: [],
      ...createStrategyDto,
    });
    return this.strategiesRepository.save(strategy);
  }

  async findAll() {
    return this.strategiesRepository.find({
      order: {
        createdAt: 'DESC',
      },
    });
  }

  async findOne(id: string) {
    const strategy = await this.strategiesRepository.findOneBy({ id });
    if (!strategy) {
      throw new NotFoundException('Strategy not found.');
    }
    return strategy;
  }
}

