from celery import shared_task
import logging

logger = logging.getLogger(__name__)
from django.core.files.storage import default_storage
import io
from core.models import IngestionJob
from core.parsers.sap import SAPParser
from core.parsers.utility import UtilityParser
from core.parsers.travel import TravelParser

@shared_task
def process_ingestion_job(job_id):
    try:
        job = IngestionJob.objects.get(id=job_id)
    except IngestionJob.DoesNotExist:
        return f"Job {job_id} not found."

    # Mark as processing
    job.status = IngestionJob.Status.PROCESSING
    job.save()

    try:
        if not job.file:
            raise ValueError("No file attached to the job")
            
        file_path = job.file.path
        
        # Open the file and parse
        with open(file_path, 'r', encoding='utf-8') as f:
            if job.source_type == IngestionJob.SourceType.SAP:
                parser = SAPParser(job)
            elif job.source_type == IngestionJob.SourceType.UTILITY:
                parser = UtilityParser(job)
            elif job.source_type == IngestionJob.SourceType.TRAVEL:
                parser = TravelParser(job)
            else:
                raise ValueError(f"Unknown source type: {job.source_type}")

            parser.parse_file(f)
            parser.save()
            
        return f"Processed job {job_id}: {job.parsed_rows} records, {job.error_rows} errors."

    except Exception as e:
        logger.exception(f"Ingestion job {job_id} failed: {str(e)}")
        job.status = IngestionJob.Status.FAILED
        job.save()
        # In a real app we'd log the exception using the python logging framework
        return f"Job {job_id} failed: {str(e)}"
