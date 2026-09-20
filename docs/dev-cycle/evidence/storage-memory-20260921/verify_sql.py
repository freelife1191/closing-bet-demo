#!/usr/bin/env python3
"""Compare original SQL arguments for migrated readiness modules without importing them."""
import ast,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[3];base=json.loads((E/'review-input.json').read_text())['base']
files=['chatbot/storage_sqlite_common.py','services/kr_market_vcp_signals_cache.py','services/kr_market_jongga_payload_helpers.py','services/kr_market_data_cache_jongga.py','services/kr_market_backtest_summary_cache.py','services/kr_market_cumulative_cache.py','services/kr_market_realtime_latest_close_cache.py','services/kr_market_realtime_market_map_cache.py','services/file_row_count_cache.py','engine/signal_tracker_source_cache.py','engine/signal_tracker_analysis_source_cache.py','engine/kr_ai_stock_info_cache.py','services/kr_market_data_cache_sqlite_payload.py','services/common_update_status_service.py','services/kr_market_realtime_price_cache.py','services/paper_trading_db_setup.py']
def sqls(text):
 tree=ast.parse(text)
 return sorted(ast.dump(n.args[0],include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('execute','executemany','executescript') and n.args)
result={}
for f in files:
 old=sqls(subprocess.check_output(['git','show',base+':'+f],cwd=R,text=True));new=sqls((R/f).read_text());result[f]={'sql_calls':len(new),'unchanged':old==new}
(E/'sql-invariance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert all(v['unchanged'] for v in result.values())
