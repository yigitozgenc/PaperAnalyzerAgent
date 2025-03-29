import os
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from mistralai import Mistral

# Logger setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class OCRProcessor:
    def __init__(self, api_key: str):
        """
        Initializes OCRProcessor with API key.
        """
        if not api_key:
            raise ValueError("API key is required for Mistral initialization.")
        
        self.client = Mistral(api_key=api_key)
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_enabled = True

    def upload_file(self, file_path: str):
        """
        Uploads the file to Mistral API.
        """
        try:
            with open(file_path, "rb") as file_handle:
                uploaded_pdf = self.client.files.upload(
                    file={
                        "file_name": Path(file_path).name,
                        "content": file_handle,
                    },
                    purpose="ocr",
                )
            logger.info(f"File uploaded successfully: {file_path}")
            return uploaded_pdf
        except Exception as e:
            logger.error(f"File upload error: {e}")
            return None

    def get_signed_url(self, uploaded_pdf):
        """
        Retrieves a signed URL for the uploaded file.
        """
        try:
            return self.client.files.get_signed_url(file_id=uploaded_pdf.id)
        except Exception as e:
            logger.error(f"Error retrieving signed URL: {e}")
            return None

    def process_ocr(self, signed_url, model: str = "mistral-ocr-latest"):
        """
        Processes OCR with the specified model.
        """
        try:
            ocr_response = self.client.ocr.process(
                model=model,
                document={
                    "type": "document_url",
                    "document_url": signed_url.url,
                },
                include_image_base64=True,
            )
            logger.info("OCR process completed successfully.")
            return ocr_response
        except Exception as e:
            logger.error(f"OCR process error: {e}")
            return None

    def get_ocr_result(self, file_path: str):
        """
        Retrieves OCR results, checks cache first.
        """
        cache_result = self._check_cache(file_path)
        if cache_result:
            logger.info(f"Using cached data: {file_path}")
            return cache_result

        uploaded_pdf = self.upload_file(file_path)
        if not uploaded_pdf:
            logger.error("File upload failed. OCR process cannot start.")
            return None

        signed_url = self.get_signed_url(uploaded_pdf)
        if not signed_url:
            logger.error("Failed to retrieve signed URL.")
            return None

        ocr_response = self.process_ocr(signed_url)
        if ocr_response:
            self._save_to_cache(file_path, ocr_response)
        return ocr_response

    def _get_cache_path(self, file_path: str) -> Path:
        """
        Generates a cache path for the file.
        """
        try:
            with open(file_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            file_stats = os.stat(file_path)
            file_hash += f"_{file_stats.st_size}_{file_stats.st_mtime}"

            return self.cache_dir / f"{file_hash}.json"
        except Exception as e:
            logger.error(f"Failed to generate cache path: {e}")
            return None

    def _check_cache(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Checks if cached OCR results exist.
        """
        cache_path = self._get_cache_path(file_path)
        if cache_path and cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                logger.info(f"Cache data loaded: {cache_path}")
                return cache_data
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        return None

    def _save_to_cache(self, file_path: str, ocr_result: Dict[str, Any]) -> None:
        """
        Saves OCR results to cache.
        """
        if not self.cache_enabled:
            return

        cache_path = self._get_cache_path(file_path)
        try:
            response_dict = json.loads(ocr_result.model_dump_json())
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(response_dict, f, ensure_ascii=False, indent=2)
            logger.info(f"OCR results cached: {cache_path}")
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")

    def _clean_cache(self, max_age_days: int = 7):
        """
        Removes old cache files.
        """
        now = time.time()
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                if cache_file.stat().st_mtime < now - max_age_days * 86400:
                    cache_file.unlink()
                    logger.info(f"Deleted old cache file: {cache_file}")
            except Exception as e:
                logger.error(f"Error cleaning cache: {e}")

    # TODO: Add cron job or background task for automatic cache cleanup.
    # TODO: Convert cache_data to OCRResponse if needed.
    # TODO: Implement retry logic for failed OCR requests.

