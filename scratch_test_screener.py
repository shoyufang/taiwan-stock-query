import os
import sys
import pandas as pd

# Reconfigure stdout to support UTF-8 printing and emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add current directory to path
sys.path.append(os.getcwd())

def test_screener():
    print("=== Testing Screener Data Loaders ===")
    from screener import get_twse_universe, _get_twse_valuation, _get_twse_institutional, filter_universe
    
    print("\n1. Testing get_twse_universe()...")
    df_univ = get_twse_universe()
    print(f"Result shape: {df_univ.shape}")
    if not df_univ.empty:
        print("Columns:", list(df_univ.columns))
        print("First 3 rows:")
        print(df_univ.head(3))
    else:
        print("WARNING: df_univ is empty!")

    print("\n2. Testing _get_twse_valuation()...")
    df_val = _get_twse_valuation()
    print(f"Result shape: {df_val.shape}")
    if not df_val.empty:
        print("Columns:", list(df_val.columns))
        print("First 3 rows:")
        print(df_val.head(3))
    else:
        print("WARNING: df_val is empty!")

    print("\n3. Testing _get_twse_institutional()...")
    df_inst = _get_twse_institutional()
    print(f"Result shape: {df_inst.shape}")
    if not df_inst.empty:
        print("Columns:", list(df_inst.columns))
        print("First 3 rows:")
        print(df_inst.head(3))
    else:
        print("WARNING: df_inst is empty!")

    print("\n4. Testing filter_universe()...")
    df_filtered = filter_universe(df_univ)
    print(f"Filtered universe size: {len(df_filtered)}")

    print("\n5. Testing screen_chip()...")
    from screener import screen_chip
    df_chip = screen_chip(df_filtered, active_conds=["foreign_buy", "trust_buy"], mode="AND")
    print(f"Chip match count (Foreign AND Trust Buy): {len(df_chip)}")
    if not df_chip.empty:
        print(df_chip.head(3))

    print("\n6. Testing screen_fundamental()...")
    from screener import screen_fundamental
    df_fund = screen_fundamental(df_filtered, pe_max=15.0, yield_min=4.0)
    print(f"Fundamental match count (PE <= 15 and Yield >= 4%): {len(df_fund)}")
    if not df_fund.empty:
        print(df_fund.head(3))

if __name__ == "__main__":
    test_screener()
