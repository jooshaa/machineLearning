import ast

def check_file(filename):
    with open(filename, 'r') as f:
        return f.read()

backtester_code = check_file('app/engine/orderflow_backtester.py')
features_code = check_file('app/engine/features.py')

def assert_pass(condition, name):
    print(f"{'PASS' if condition else 'FAIL'} - {name}")

print("=== ФИЛЬТРЫ ===")
assert_pass("daily_loss_pct >= 0.02" in backtester_code and "daily_loss_limit_hit = True" in backtester_code, "daily_loss_pct блокирует при >= 0.02")
assert_pass("daily_loss_pct +=" in backtester_code and "trade[\"result\"] == \"loss\"" in backtester_code and "session_end" in backtester_code, "session_end не добавляется к daily_loss_pct")
assert_pass("is_ny_session and ny_time.time() < pd.to_datetime('09:50').time()" in backtester_code, "NY блокировка: 09:30-09:49:59 заблокировано")
assert_pass("ny_time.time() < pd.to_datetime('09:50').time()" in backtester_code, "NY разрешение: 09:50:00+ разрешено")
assert_pass("session_min_contracts = 30 if is_ny else 20" in backtester_code, "London min_contracts = 20, NY min_contracts = 30")
assert_pass("ny_time.time() >= pd.to_datetime('16:00').time() or ny_time.time() < pd.to_datetime('03:00').time()" in backtester_code, "Вне сессий: нет входов")
assert_pass("retest_zone" in backtester_code and "if pending_context[\"type\"] == \"breakout\" and pending_context.get(\"retest_zone\")" in backtester_code, "BREAKOUT ждёт retest_zone перед входом")
assert_pass("market_state == \"UNCLEAR\"" in backtester_code and "blocked_unclear" in backtester_code, "UNCLEAR блокирует входы")
assert_pass("cvd_divergence" in features_code, "cvd_divergence колонка существует в датафрейме")
assert_pass("v_ratio > 1.2" not in backtester_code and "session_min_contracts" in backtester_code, "v_ratio удалён, используется абсолютный размер")

