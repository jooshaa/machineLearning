import pandas as pd
from typing import Dict, Any, List
import bisect

class OrderBookL3:
    def __init__(self):
        # order_id -> { "price": p, "size": s, "side": 'A'/'B' }
        self.orders: Dict[int, Dict[str, Any]] = {}
        
        # Sorted prices for fast best bid/ask access
        self.bid_prices: List[float] = [] # Sorted ascending
        self.ask_prices: List[float] = [] # Sorted ascending
        
        # price -> { "bid_size": float, "ask_size": float }
        self.levels: Dict[float, Dict[str, float]] = {}
        
        self.best_bid = 0.0
        self.best_ask = float('inf')
        self.total_bid_liquidity = 0.0
        self.total_ask_liquidity = 0.0

    def _update_level(self, price: float, delta: float, side: str):
        if price not in self.levels:
            self.levels[price] = {"bid_size": 0.0, "ask_size": 0.0}
            
        level = self.levels[price]
        if side == 'B':
            self.total_bid_liquidity += delta
            old_size = level["bid_size"]
            level["bid_size"] += delta
            # Manage sorted list for best bid
            if old_size == 0 and level["bid_size"] > 0:
                bisect.insort(self.bid_prices, price)
            elif old_size > 0 and level["bid_size"] <= 0:
                # Remove price from list if size becomes zero
                idx = bisect.bisect_left(self.bid_prices, price)
                if idx < len(self.bid_prices) and self.bid_prices[idx] == price:
                    self.bid_prices.pop(idx)
        else:
            self.total_ask_liquidity += delta
            old_size = level["ask_size"]
            level["ask_size"] += delta
            if old_size == 0 and level["ask_size"] > 0:
                bisect.insort(self.ask_prices, price)
            elif old_size > 0 and level["ask_size"] <= 0:
                idx = bisect.bisect_left(self.ask_prices, price)
                if idx < len(self.ask_prices) and self.ask_prices[idx] == price:
                    self.ask_prices.pop(idx)

        self.best_bid = self.bid_prices[-1] if self.bid_prices else 0.0
        self.best_ask = self.ask_prices[0] if self.ask_prices else float('inf')

    def apply_event(self, action: str, order_id: int, price: float, size: float, side: str):
        if action == 'A':  # Add
            self.orders[order_id] = {"price": price, "size": size, "side": side}
            self._update_level(price, size, side)
            
        elif action == 'C':  # Cancel
            if order_id in self.orders:
                old = self.orders.pop(order_id)
                self._update_level(old["price"], -old["size"], old["side"])

        elif action == 'M':  # Modify
            if order_id in self.orders:
                old = self.orders[order_id]
                delta_size = size - old["size"]
                old["size"] = size
                self._update_level(old["price"], delta_size, old["side"])

        elif action in ['T', 'F', 'V']:  # Trade / Fill / Trade-summary
            if order_id in self.orders:
                old = self.orders[order_id]
                trade_size = min(size, old["size"])
                old["size"] -= trade_size
                self._update_level(old["price"], -trade_size, old["side"])
                if old["size"] <= 0:
                    self.orders.pop(order_id)
            
            # Crucial: Even if order wasn't in our window, the TRADE is real.
            # We return True to indicate an event should be recorded.
            return True
        return False

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "total_bid_liquidity": self.total_bid_liquidity,
            "total_ask_liquidity": self.total_ask_liquidity
        }

def process_mbo_stream(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Highly optimized L3 processing.
    """
    book = OrderBookL3()
    events = []
    
    print(f"[DEBUG] Raw MBO rows: {len(df)}")
    
    # Фильтруем спреды и аномальные цены до цикла
    symbol_filter_mask = pd.Series(True, index=df.index)
    if "symbol" in df.columns:
        symbol_filter_mask = ~df["symbol"].str.contains("-", na=False)
    
    df_filtered_sym = df[symbol_filter_mask]
    print(f"[DEBUG] Rows after symbol filter: {len(df_filtered_sym)}")
    
    price_filter_mask = (df_filtered_sym["price"] > 1000) & (df_filtered_sym["price"] < 90000)
    df = df_filtered_sym[price_filter_mask]
    
    print(f"[DEBUG] Rows after price filter (1000-90000): {len(df)}")

    itertuples = df.itertuples()
    
    total_processed = 0
    trade_actions = 0
    add_actions = 0
    cancel_actions = 0
    modify_actions = 0
    
    for row in itertuples:
        total_processed += 1
        action = row.action
        if action == 'A': add_actions += 1
        elif action == 'C': cancel_actions += 1
        elif action == 'M': modify_actions += 1
        
        is_trade = book.apply_event(
            action=action,
            order_id=row.order_id,
            price=row.price,
            size=row.size,
            side=row.side
        )
        
        if is_trade:
            trade_actions += 1
            events.append({
                "ts": row.Index,
                "price": row.price,
                "size": row.size,
                "side": row.side,
                "best_bid": book.best_bid,
                "best_ask": book.best_ask,
                "total_bid_liquidity": book.total_bid_liquidity,
                "total_ask_liquidity": book.total_ask_liquidity
            })
            
    print(f"[DEBUG] Iteration summary:")
    print(f"  - Total processed rows: {total_processed}")
    print(f"  - Add actions: {add_actions}")
    print(f"  - Cancel actions: {cancel_actions}")
    print(f"  - Modify actions: {modify_actions}")
    print(f"  - Trade actions (triggers): {trade_actions}")
    print(f"  - Total events recorded: {len(events)}")
    return events
