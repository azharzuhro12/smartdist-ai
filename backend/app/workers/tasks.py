import logging
from typing import Any, Dict, Optional
from backend.app.db.session import SessionLocal
from backend.app.services.etl_service import ETLService
from backend.app.workers.celery_app import celery_app
from ml.pipelines.common.constants import DATASET_NAME_STORE_SALES
from ml.pipelines.ingestion.extract import DataExtractor
from ml.pipelines.synthetic.inventory_generator import SyntheticInventoryGenerator
from ml.pipelines.validation.quality import DataQualityValidator

logger = logging.getLogger("smartdist.celery")


@celery_app.task(bind=True, name="backend.app.workers.tasks.verify_infrastructure")
def verify_infrastructure(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Sample verification task to test Celery execution and Redis connectivity."""
    task_id = self.request.id
    logger.info(f"Executing verify_infrastructure task: task_id={task_id}, payload={payload}")
    return {
        "status": "success",
        "task_id": task_id,
        "message": "Celery infrastructure worker verified successfully.",
        "input_payload": payload or {},
    }


@celery_app.task(bind=True, name="backend.app.workers.tasks.import_sales_dataset")
def import_sales_dataset(
    self,
    max_sales_rows: Optional[int] = 50_000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Background Celery task to execute the sales ingestion and transformation pipeline.
    """
    task_id = self.request.id
    logger.info(f"Starting import_sales_dataset task: task_id={task_id}, max_rows={max_sales_rows}")
    try:
        result = ETLService.execute_pipeline(
            max_sales_rows=max_sales_rows, start_date=start_date, end_date=end_date
        )
        result["task_id"] = task_id
        logger.info(f"import_sales_dataset completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"import_sales_dataset failed: {exc}", exc_info=True)
        return {
            "status": "FAILED",
            "task_id": task_id,
            "error": str(exc),
        }


@celery_app.task(bind=True, name="backend.app.workers.tasks.validate_dataset")
def validate_dataset(self) -> Dict[str, Any]:
    """
    Background Celery task to execute data quality checks on raw stores and catalog data.
    """
    task_id = self.request.id
    logger.info(f"Starting validate_dataset task: task_id={task_id}")
    db = SessionLocal()
    try:
        stores_df = DataExtractor.extract_stores()
        _, summary = DataQualityValidator.validate_stores_data(stores_df)
        DataQualityValidator.save_quality_result(db, DATASET_NAME_STORE_SALES, summary)
        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "quality_summary": summary,
        }
    except Exception as exc:
        logger.error(f"validate_dataset failed: {exc}", exc_info=True)
        return {"status": "FAILED", "task_id": task_id, "error": str(exc)}
    finally:
        db.close()


@celery_app.task(bind=True, name="backend.app.workers.tasks.generate_synthetic_inventory")
def generate_synthetic_inventory(self, seed: int = 42) -> Dict[str, Any]:
    """
    Background task to generate or refresh synthetic warehouses, suppliers, and stock levels.
    """
    task_id = self.request.id
    logger.info(f"Starting generate_synthetic_inventory task: task_id={task_id}, seed={seed}")
    db = SessionLocal()
    try:
        generator = SyntheticInventoryGenerator(seed=seed)
        warehouses = generator.generate_warehouses(db)
        suppliers = generator.generate_suppliers(db)
        stats = generator.generate_product_suppliers_and_inventory(db, warehouses, suppliers)
        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "warehouses_count": len(warehouses),
            "suppliers_count": len(suppliers),
            "inventory_records": stats["inventory_records"],
        }
    except Exception as exc:
        logger.error(f"generate_synthetic_inventory failed: {exc}", exc_info=True)
        return {"status": "FAILED", "task_id": task_id, "error": str(exc)}
    finally:
        db.close()


@celery_app.task(bind=True, name="backend.app.workers.tasks.detect_sales_anomalies")
def detect_sales_anomalies(
    self,
    start_date: str,
    end_date: str,
    branch_id: Optional[int] = None,
    product_id: Optional[int] = None,
    sensitivity: float = 1.0,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Asynchronous Celery task executing batch sales anomaly detection.
    """
    task_id = self.request.id
    logger.info(f"Starting detect_sales_anomalies task {task_id}: {start_date} to {end_date}")
    db = SessionLocal()
    try:
        from backend.app.services.anomaly_service import AnomalyDetectionService
        run = AnomalyDetectionService.execute_detection_run(
            db=db,
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id,
            product_id=product_id,
            sensitivity=sensitivity,
            custom_weights=weights,
        )
        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "run_id": run.id,
            "total_observations": run.total_observations,
            "anomalies_detected": run.anomalies_detected,
        }
    except Exception as exc:
        logger.error(f"detect_sales_anomalies task {task_id} failed: {exc}", exc_info=True)
        return {"status": "FAILED", "task_id": task_id, "error": str(exc)}
    finally:
        db.close()
