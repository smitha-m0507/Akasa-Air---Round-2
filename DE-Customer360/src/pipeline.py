import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import setup_logging
from .db import write_outputs
from .ingest import ingest_all
from .insights import build_insights
from .merge import merge_customer360
from .quality import run_quality
from .transform import get_lineage, standardize_df


def _step(name, fn, steps, logger):
    start = time.time()
    try:
        result = fn()
        steps.append({"step": name, "status": "success", "seconds": round(time.time() - start, 3), "detail": result.get("detail", "")})
        logger.info("step=%s status=success detail=%s", name, result.get("detail", ""))
        return result["data"]
    except Exception as exc:
        steps.append({"step": name, "status": "error", "seconds": round(time.time() - start, 3), "detail": str(exc)})
        logger.exception("step=%s status=error", name)
        raise


def run_pipeline(base_dir, config):
    logger = setup_logging(base_dir, config.get("log_path", "logs/pipeline.log"))
    steps = []

    raw = _step("Ingest sources", lambda: {"data": ingest_all(base_dir, config), "detail": "Loaded JSON, CSV, XML"}, steps, logger)

    def standardize():
        data = {k: standardize_df(v, k) for k, v in raw.items()}
        detail = ", ".join(f"{k}:{len(v)}" for k, v in data.items())
        return {"data": data, "detail": detail}

    standardized = _step("Standardize schemas", standardize, steps, logger)

    report, issue_samples = _step(
        "Run data quality checks",
        lambda: {"data": run_quality(raw, standardized, config), "detail": "Generated DQ report and issue samples"},
        steps,
        logger,
    )

    customer360 = _step(
        "Merge Customer 360",
        lambda: {"data": merge_customer360(standardized), "detail": f"{len(merge_customer360(standardized))} unified records"},
        steps,
        logger,
    )
    # recalc detail using actual customer360
    steps[-1]["detail"] = f"{len(customer360)} unified records"

    insights = _step(
        "Generate insights",
        lambda: {"data": build_insights(customer360, config), "detail": "Top 10, segments, support risk, regional"},
        steps,
        logger,
    )

    customer360_segmented = insights["customer360_segmented"]
    required_ok = customer360_segmented["customer_id"].notna() if "customer_id" in customer360_segmented.columns else customer360_segmented.index == -1
    for field in config.get("required_fields", []):
        if field in customer360_segmented.columns:
            required_ok &= customer360_segmented[field].notna() & (customer360_segmented[field].astype(str).str.strip() != "")
    report["successful_records"] = int(required_ok.sum()) if len(customer360_segmented) else 0

    output_dir = Path(base_dir) / config.get("output_dir", "data/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    customer360_segmented.to_json(output_dir / "customer_360.json", orient="records", indent=2, force_ascii=False)
    customer360_segmented.to_csv(output_dir / "customer_360.csv", index=False)
    with open(output_dir / "data_quality_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    for name, df in [("top10_revenue", insights["top10_revenue"]), ("segments", insights["segments"]), ("support_risk", insights["support_risk"]), ("regional_analytics", insights["regional"])]:
        df.to_csv(output_dir / f"{name}.csv", index=False)
    issue_samples.to_csv(output_dir / "quality_issues.csv", index=False)

    write_outputs(base_dir, config.get("db_path", "data/output/customer360.db"), customer360_segmented, report, insights, issue_samples)

    run_summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_counts": {k: len(v) for k, v in raw.items()},
        "report": report,
        "steps": steps,
        "outputs": [str((output_dir / n).as_posix()) for n in ["customer_360.json", "customer_360.csv", "data_quality_report.json"]],
    }
    with open(output_dir / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2)

    logger.info("pipeline complete report=%s", report)
    return {
        "raw": raw,
        "standardized": standardized,
        "report": report,
        "issue_samples": issue_samples,
        "customer360": customer360_segmented,
        "insights": insights,
        "steps": steps,
        "run_summary": run_summary,
        "lineage": get_lineage(),
    }
