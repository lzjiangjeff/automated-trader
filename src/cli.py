
#!/usr/bin/env python3
import argparse
import yaml
from src.data.polygon_client import PolygonClient
from src.engine.backtest import BacktestEngine
from src.execution.ib_adapter import IBAdapter
from pathlib import Path

def cmd_update_data(args):
    client = PolygonClient(api_key_env='POLYGON_API_KEY')
    df = client.download_daily(symbol=args.symbol.upper())
    print(f"Downloaded {len(df)} rows for {args.symbol.upper()}. Cached to {client.cache_path}")

def cmd_backtest(args):
    cfg = yaml.safe_load(open(args.config))
    client = PolygonClient(api_key_env='POLYGON_API_KEY')
    df = client.load_cached(symbol=cfg['data']['symbol'], frequency=cfg['data'].get('frequency','1d'))
    engine = BacktestEngine(df, config=cfg)
    results = engine.run_all_strategies()
    print("--- Backtest summary ---")
    for name, stats in results.items():
        print(f"Strategy: {name}")
        for k,v in stats.items():
            print(f"  {k}: {v}")
        print()

def cmd_paper_trade(args):
    # Uses mocked IB adapter by default
    adapter = IBAdapter(mode='paper')
    print('IB Adapter status:', adapter.status())

def main():
    parser = argparse.ArgumentParser(prog='tqqq-trader')
    sub = parser.add_subparsers(dest='cmd')
    u = sub.add_parser('update-data')
    u.add_argument('--symbol', default='TQQQ')
    b = sub.add_parser('backtest')
    b.add_argument('--config', default='configs/example_daily.yaml')
    p = sub.add_parser('paper-trade')
    args = parser.parse_args()
    if args.cmd == 'update-data':
        cmd_update_data(args)
    elif args.cmd == 'backtest':
        cmd_backtest(args)
    elif args.cmd == 'paper-trade':
        cmd_paper_trade(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
