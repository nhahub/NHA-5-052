"""
Failure-path tests for prices_daily_dag.py and sales_daily_dag.py.

Airflow is NOT required - the DAG files are parsed with `ast`, so these tests
run anywhere Python runs. They verify the structural guarantees that make a
failed task actually fail the pipeline:

  1. Every expected task_id is declared as a PythonOperator.
  2. The downstream chain is linear: extract >> store >> load >> check.
  3. catchup=False  -> a past failed run is not silently backfilled.
  4. retries >= 1   -> transient failures are retried.
  5. quality_check wraps check_prices / check_sales WITHOUT an except clause
     that would swallow the ValueError.
  6. _load_prices calls run_prices; _run_etl calls run_etl from automation.
  7. Known open item: TODO N5 is still present (documented, delete test once fixed).

Run: python 05_etl/tests/test_dag_failure_paths.py
"""
import ast
import sys
import traceback
from pathlib import Path

DAGS = Path(__file__).resolve().parents[1] / "dags"
PRICES = DAGS / "prices_daily_dag.py"
SALES = DAGS / "sales_daily_dag.py"


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _calls_by_name(tree, name):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == name]


def _kwarg(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _task_ids(tree):
    ids = set()
    for call in _calls_by_name(tree, "PythonOperator"):
        tid = _kwarg(call, "task_id")
        if isinstance(tid, ast.Constant) and isinstance(tid.value, str):
            ids.add(tid.value)
    return ids


def _function_defs(tree):
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def _dag_kwargs(tree):
    calls = _calls_by_name(tree, "DAG")
    assert calls, "no DAG(...) call found"
    return {kw.arg: _literal(kw.value) for kw in calls[0].keywords}


# ------------------------------------------------------------ static source
def test_prices_dag_file_exists():
    assert PRICES.is_file(), f"missing: {PRICES}"


def test_sales_dag_file_exists():
    assert SALES.is_file(), f"missing: {SALES}"


# ------------------------------------------------------------ prices_daily_dag
def test_prices_dag_declares_all_task_ids():
    # Static PythonOperator(task_id="...") for the store/load/check tasks.
    ids = _task_ids(_parse(PRICES))
    static_required = {
        "store_offers_mongodb", "validate_match_load_prices", "quality_check",
    }
    missing_static = static_required - ids
    assert not missing_static, \
        f"missing static task_ids in prices_daily_dag: {missing_static}"

    # The three extract tasks use task_id=f"extract_{site}" inside a list
    # comprehension, so AST cannot resolve the value. Verify the source
    # declares the f-string template AND the exact three site names.
    text = PRICES.read_text(encoding="utf-8")
    assert 'task_id=f"extract_{site}"' in text, \
        "prices_daily_dag must declare extract tasks via task_id=f\"extract_{site}\""
    for site in ("dream2000", "xprs", "elghazawy"):
        assert f'"{site}"' in text, \
            f"prices_daily_dag must include site {site!r} in the extract loop"
    assert 'SITES = ("dream2000", "xprs", "jumia")' not in text, "jumia is no longer scraped (HTTP 403 since 2-Nov)"


def test_prices_dag_chain_is_linear():
    text = PRICES.read_text(encoding="utf-8")
    assert "extract >> store >> load >> check" in text, \
        "prices_daily_dag chain must be 'extract >> store >> load >> check'"


def test_prices_dag_catchup_disabled():
    kw = _dag_kwargs(_parse(PRICES))
    assert kw.get("catchup") is False, f"catchup must be False, got {kw.get('catchup')}"


def test_prices_dag_max_active_runs_one():
    kw = _dag_kwargs(_parse(PRICES))
    assert kw.get("max_active_runs") == 1, \
        f"max_active_runs must be 1, got {kw.get('max_active_runs')}"


def test_prices_dag_retries_configured():
    tree = _parse(PRICES)
    text = PRICES.read_text(encoding="utf-8")
    assert '"retries": 3' in text or "'retries': 3" in text, \
        "default_args must set retries: 3"


def test_prices_quality_check_calls_check_prices():
    tree = _parse(PRICES)
    fn = _function_defs(tree)["_quality_check"]
    names = [n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "check_prices" in names, "_quality_check must call check_prices()"


def test_prices_quality_check_does_not_swallow_errors():
    tree = _parse(PRICES)
    fn = _function_defs(tree)["_quality_check"]
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            assert not node.handlers, \
                "_quality_check must NOT have except handlers - it would swallow errors"


def test_prices_load_prices_calls_run_prices():
    tree = _parse(PRICES)
    fn = _function_defs(tree)["_load_prices"]
    names = [n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "run_prices" in names, "_load_prices must call run_prices()"


def test_prices_block_fails_without_retry():
    """HTTP 403 (BlockedError) must become AirflowFailException: Airflow does not retry it (no second visit)."""
    tree = _parse(PRICES)
    fn = _function_defs(tree)["_scrape"]
    raised = {n.exc.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and isinstance(n.exc.func, ast.Name)}
    handlers = [h for h in ast.walk(fn) if isinstance(h, ast.ExceptHandler)]
    assert any(isinstance(h.type, ast.Name) and h.type.id == "BlockedError" for h in handlers), \
        "_scrape must catch BlockedError"
    assert "AirflowFailException" in raised, "_scrape must raise AirflowFailException on BlockedError"


def test_prices_store_runs_when_one_site_failed():
    """store_offers_mongodb uses trigger_rule ALL_DONE so one blocked site does not lose the other sites' day."""
    tree = _parse(PRICES)
    for call in _calls_by_name(tree, "PythonOperator"):
        tid = _kwarg(call, "task_id")
        if isinstance(tid, ast.Constant) and tid.value == "store_offers_mongodb":
            rule = _kwarg(call, "trigger_rule")
            assert rule is not None and "ALL_DONE" in ast.unparse(rule), "store_offers_mongodb needs ALL_DONE"
            return
    raise AssertionError("store_offers_mongodb task not found")


def test_prices_quality_check_does_not_use_ds():
    """ds is the day BEFORE the run of a daily DAG; the check must use the dates the load processed."""
    tree = _parse(PRICES)
    fn = _function_defs(tree)["_quality_check"]
    args = [a.arg for a in fn.args.args]
    assert "ds" not in args, "_quality_check must not take ds"
    assert "xcom_pull" in ast.unparse(fn), "_quality_check must read the loaded dates from XCom"


# ------------------------------------------------------------ sales_daily_dag
def test_sales_dag_declares_all_task_ids():
    ids = _task_ids(_parse(SALES))
    required = {
        "generate_orders_csv", "load_orders_mysql",
        "extract_validate_transform_load", "quality_check",
    }
    missing = required - ids
    assert not missing, f"missing task_ids in sales_daily_dag: {missing}"


def test_sales_dag_chain_is_linear():
    text = SALES.read_text(encoding="utf-8")
    assert "generate >> load_mysql >> etl >> check" in text, \
        "sales_daily_dag chain must be 'generate >> load_mysql >> etl >> check'"


def test_sales_dag_catchup_disabled():
    kw = _dag_kwargs(_parse(SALES))
    assert kw.get("catchup") is False, f"catchup must be False, got {kw.get('catchup')}"


def test_sales_dag_max_active_runs_one():
    kw = _dag_kwargs(_parse(SALES))
    assert kw.get("max_active_runs") == 1, \
        f"max_active_runs must be 1, got {kw.get('max_active_runs')}"


def test_sales_dag_retries_configured():
    text = SALES.read_text(encoding="utf-8")
    assert '"retries": 3' in text or "'retries': 3" in text, \
        "default_args must set retries: 3"


def test_sales_quality_check_calls_check_sales():
    tree = _parse(SALES)
    fn = _function_defs(tree)["_quality_check"]
    names = [n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "check_sales" in names, "_quality_check must call check_sales()"


def test_sales_quality_check_does_not_swallow_errors():
    tree = _parse(SALES)
    fn = _function_defs(tree)["_quality_check"]
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            assert not node.handlers, \
                "_quality_check must NOT have except handlers - it would swallow errors"


def test_sales_run_etl_calls_automation_run_etl():
    tree = _parse(SALES)
    fn = _function_defs(tree)["_run_etl"]
    names = [n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "run_etl" in names, "_run_etl must call automation.run_etl()"


def test_sales_generate_orders_calls_generate_sales_script():
    tree = _parse(SALES)
    fn = _function_defs(tree)["_generate_orders"]
    src = ast.unparse(fn)
    assert "_run(" in src and "generate_sales.py" in src, "_generate_orders must run generate_sales.py through _run(...)"
    helper = ast.unparse(_function_defs(tree)["_run"])
    assert "subprocess.run" in helper and "check=True" in helper, "_run must use subprocess.run(..., check=True)"


def test_sales_load_mysql_calls_load_batch_script():
    tree = _parse(SALES)
    fn = _function_defs(tree)["_load_mysql"]
    src = ast.unparse(fn)
    assert "_run(" in src and "load_batch.py" in src, "_load_mysql must run load_batch.py through _run(...)"
    helper = ast.unparse(_function_defs(tree)["_run"])
    assert "subprocess.run" in helper and "check=True" in helper, "_run must use subprocess.run(..., check=True)"


def test_sales_refreshes_reference_and_report_view():
    """Products are rebuilt before the orders, and the materialized view is refreshed after the check."""
    ids = _task_ids(_parse(SALES))
    assert {"refresh_reference_data", "refresh_report_view"} <= ids, ids
    text = SALES.read_text(encoding="utf-8")
    assert "reference >> generate >> load_mysql >> etl >> check >> refresh" in text
    assert "REFRESH MATERIALIZED VIEW mv_our_price_vs_market" in text


# ------------------------------------------------------------ main
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
