#!/usr/bin/env python3
"""
SmartDist AI - Staged Historical Data Ingestion Tool
Progressively and idempotently loads Store Sales history into PostgreSQL.
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.logging import logger, setup_logging
from backend.app.db.session import SessionLocal
from backend.app.models.business import DailySale
from backend.app.services.etl_service import ETLService
from sqlalchemy import func, select


def run_staged_ingestion(stages: list[tuple[str, str]]) -> None:
    """Execute ingestion in manageable date stages to prevent timeouts and high memory usage."""
    setup_logging(log_level="INFO", log_format="standard")
    logger.info(f"Initiating historical ingestion across {len(stages)} stages...")

    db = SessionLocal()
    initial_count = db.scalar(select(func.count(DailySale.id))) or 0
    db.close()
    logger.info(f"Initial daily_sales records in database: {initial_count}")

    overall_start = time.time()
    total_new_rows = 0

    for idx, (start_d, end_d) in enumerate(stages, 1):
        stage_start = time.time()
        logger.info(f"[{idx}/{len(stages)}] Starting stage: {start_d} to {end_d}...")

        try:
            res = ETLService.execute_pipeline(
                start_date=start_d,
                end_date=end_d,
                max_sales_rows=None,
            )
            elapsed = time.time() - stage_start
            inserted = res.get("sales_records_inserted", 0)
            total_new_rows += inserted
            logger.info(
                f"[{idx}/{len(stages)}] Completed stage {start_d} -> {end_d} in {elapsed:.1f}s: "
                f"{inserted} sales records upserted."
            )
        except Exception as exc:
            logger.error(f"Stage {start_d} -> {end_d} failed: {exc}", exc_info=True)
            raise exc

    overall_elapsed = time.time() - overall_start
    db = SessionLocal()
    final_count = db.scalar(select(func.count(DailySale.id))) or 0
    date_range = db.execute(
        select(func.min(DailySale.sale_date), func.max(DailySale.sale_date))
    ).one()
    db.close()

    logger.info("=" * 60)
    logger.info(f"Historical ingestion completed in {overall_elapsed / 60:.2f} minutes.")
    logger.info(f"Final daily_sales records: {final_count} (Delta: +{final_count - initial_count})")
    logger.info(f"Database date range: {date_range[0]} to {date_range[1]}")
    logger.info("=" * 60)


def generate_quarterly_stages(start_year: int = 2013, end_year: int = 2017) -> list[tuple[str, str]]:
    """Generate quarterly date intervals from 2013-01-01 to 2017-08-15."""
    quarters = []
    for y in range(start_year, end_year + 1):
        if y == 2017:
            quarters.extend([
                (f"{y}-01-01", f"{y}-03-31"),
                (f"{y}-04-01", f"{y}-06-30"),
                (f"{y}-07-01", f"{y}-08-15"),
            ])
        else:
            quarters.extend([
                (f"{y}-01-01", f"{y}-03-31"),
                (f"{y}-04-01", f"{y}-06-30"),
                (f"{y}-07-01", f"{y}-09-30"),
                (f"{y}-10-01", f"{y}-12-31"),
            ])
    return quarters


def main():
    parser = argparse.ArgumentParser(description="SmartDist AI Historical Sales Ingestion Tool")
    parser.add_argument("--all", action="store_true", help="Ingest all 4.5 years (2013-01-01 to 2017-08-15) in quarterly stages")
    parser.add_argument("--year", type=int, choices=range(2013, 2018), help="Ingest a specific calendar year")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")

    args = parser.parse_args()

    if args.all:
        stages = generate_quarterly_stages(2013, 2017)
    elif args.year:
        stages = [q for q in generate_quarterly_stages(args.year, args.year)]
    elif args.start_date and args.end_date:
        stages = [(args.start_date, args.end_date)]
    else:
        parser.print_help()
        sys.exit(1)

    run_staged_ingestion(stages)


if __name__ == "__main__":
    main()
