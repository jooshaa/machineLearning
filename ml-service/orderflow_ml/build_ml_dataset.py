import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def extract_l3_features(timestamp_utc, direction, entry_price):
    """
    Placeholder/Scaffolding для экстракции фичей из L3/MBO данных.
    В реальности здесь должен быть коннектор к вашей базе данных с L3 orderflow.
    """
    # Пример того, какие фичи мы ожидаем получить из ядра MBO/L3:
    
    # Чтобы скрипт работал сейчас как демо, генерируем синтетические фичи с небольшим шумом.
    # В реальном коде вы замените этот блок на реальные запросы к MBO данным за период [timestamp - 5m, timestamp]
    
    np.random.seed(int(timestamp_utc.timestamp()) % 100000)
    
    is_buy = 1 if direction.lower() == 'buy' else -1
    
    features = {
        # 1. Orderflow & Delta
        'cvd_slope_1m': np.random.normal(is_buy * 10, 20),
        'cvd_slope_5m': np.random.normal(is_buy * 25, 50),
        'delta_velocity': np.random.normal(is_buy * 5, 10), # rate of change
        'aggressive_ratio': np.random.uniform(0.5, 2.0) if is_buy == 1 else np.random.uniform(0.1, 1.5),
        
        # 2. Liquidity & Absorption
        # Absorption score: высокий скор означает, что лимиты обновляются и поглощают агрессивные маркет ордера
        'absorption_score_bid': np.random.uniform(0, 100),
        'absorption_score_ask': np.random.uniform(0, 100),
        'replenishment_rate_ms': np.random.uniform(10, 500), # скорость пополнения ликвидности
        
        # 3. HTF Context
        'dist_to_poc_ticks': np.random.normal(0, 50),
        'dist_to_vwap_ticks': np.random.normal(0, 30),
        'atr_percentile': np.random.uniform(0.1, 0.9), # Насколько текущая волатильность высока
        
        # 4. Continuation Quality (Immediate post-entry or micro-momentum pre-entry)
        'imbalance_score': np.random.uniform(0, 10) * is_buy,
        'tape_speed_tps': np.random.uniform(10, 200) # trades per second (активность)
    }
    
    # Дополнительная производная фича: направленная абсорбция
    features['directional_absorption'] = features['absorption_score_bid'] if is_buy == 1 else features['absorption_score_ask']
    
    return features

def build_dataset(json_path, output_csv_path):
    print(f"Loading trades from {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        trades = json.load(f)
        
    dataset_rows = []
    
    for t in trades:
        # Извлекаем метадату сделки
        try:
            utc_dt = datetime.strptime(t['utcDatetime'], "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            try:
                utc_dt = datetime.strptime(t['utcDatetime'], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                utc_dt = datetime.fromtimestamp(t['id'] / 1000.0)
            
        direction = t.get('direction', 'Buy')
        entry_price = t.get('entryPrice', 0)
        result = t.get('result', 'Loss')
        outcome_r = t.get('outcomeR', 0)
        
        # Определяем таргет: 1 если хороший сетап (Win), 0 если плохой (Loss/BE)
        is_good_setup = 1 if result.lower() == 'win' else 0
        
        # Извлекаем MBO/L3 фичи вокруг точки входа
        mbo_features = extract_l3_features(utc_dt, direction, entry_price)
        
        # Собираем строку данных
        row = {
            'trade_id': t['id'],
            'timestamp_utc': utc_dt,
            'direction': direction,
            'entry_price': entry_price,
            'outcome_r': outcome_r,
            'target_is_good_setup': is_good_setup
        }
        row.update(mbo_features)
        dataset_rows.append(row)
        
    df = pd.DataFrame(dataset_rows)
    df.to_csv(output_csv_path, index=False)
    print(f"Successfully generated ML dataset with {len(df)} rows and {len(df.columns)} columns.")
    print(f"Saved to {output_csv_path}")

if __name__ == "__main__":
    TRADES_JSON_PATH = "/Users/asal/Desktop/trades(6).json"
    OUTPUT_CSV_PATH = "/Users/asal/Desktop/own/machine learning/ml-service/orderflow_ml/ml_dataset.csv"
    build_dataset(TRADES_JSON_PATH, OUTPUT_CSV_PATH)
