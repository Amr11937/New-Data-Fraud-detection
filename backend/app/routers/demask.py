"""
Demask -- batch-convert masked subscriber IDs back to originals, via a
parquet mapping lookup or a pluggable decryption provider. The input file
is a CSV, the mapping file is parquet, and results download as CSV.

Ported and merged from chinthakadd7/Demask (backend/routers/mapping.py +
backend/routers/encryption.py), mounted under this app's existing CORS
and router-registration conventions instead of running as a standalone
service.
"""

import io
import os

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..demask.encryption_provider import ENCRYPTION_REGISTRY, EncryptionProvider
from ..demask.mapping_provider import MappingProvider

router = APIRouter(prefix="/api/demask", tags=["demask"])

_mapping_provider = MappingProvider()
_encryption_provider = EncryptionProvider()

_RESULT_HEADERS_EXPOSE = "X-Total-Records, X-Processed, X-Unprocessed, X-Errors"


def _read_csv(data: bytes) -> pd.DataFrame:
    # Read as strings to preserve phone numbers and prevent dtype mismatch.
    return pd.read_csv(io.BytesIO(data), dtype=str)


def _read_parquet(data: bytes) -> pd.DataFrame:
    # Handled as strings too, so ID columns never mismatch on dtype.
    return pd.read_parquet(io.BytesIO(data)).astype("string")


def _csv_response(df: pd.DataFrame, filename: str, headers: dict) -> StreamingResponse:
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    headers = {**headers, "Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([csv_bytes]), media_type="text/csv", headers=headers)


@router.post("/mapping")
async def process_mapping(
    input_file: UploadFile = File(...),
    mapping_file: UploadFile = File(...),
    input_id_col: str = Form("subscriber_id"),
    mapping_masked_col: str = Form("masked_subscriber_id"),
    mapping_original_col: str = Form("original_subscriber_id"),
):
    # Input is a CSV and the mapping is parquet; both are read as strings
    try:
        input_df = _read_csv(await input_file.read())
    except Exception as exc:
        raise HTTPException(400, f"Could not parse input CSV: {exc}") from exc

    try:
        mapping_df = _read_parquet(await mapping_file.read())
    except Exception as exc:
        raise HTTPException(400, f"Could not parse mapping parquet file: {exc}") from exc

    if input_id_col not in input_df.columns:
        raise HTTPException(422, f"Column '{input_id_col}' not found in input CSV. Available: {list(input_df.columns)}")
    if mapping_masked_col not in mapping_df.columns:
        raise HTTPException(422, f"Column '{mapping_masked_col}' not found in mapping file. Available: {list(mapping_df.columns)}")
    if mapping_original_col not in mapping_df.columns:
        raise HTTPException(422, f"Column '{mapping_original_col}' not found in mapping file. Available: {list(mapping_df.columns)}")

    try:
        result = _mapping_provider.process(
            df=input_df,
            mapping_df=mapping_df,
            input_id_col=input_id_col,
            mapping_masked_col=mapping_masked_col,
            mapping_original_col=mapping_original_col,
        )
    except Exception as exc:
        raise HTTPException(500, f"Processing error: {exc}") from exc

    headers = {
        "X-Total-Records": str(result.total_records),
        "X-Processed": str(result.processed),
        "X-Unprocessed": str(result.unprocessed),
        "X-Errors": str(result.errors),
        "Access-Control-Expose-Headers": _RESULT_HEADERS_EXPOSE,
    }
    return _csv_response(result.dataframe, "updated_subscribers.csv", headers)


@router.get("/encryption/methods")
async def get_encryption_methods():
    methods = list(ENCRYPTION_REGISTRY.keys())
    configured_default = os.environ.get("ENCRYPTION_PROVIDER", "")
    default_method = configured_default if configured_default in ENCRYPTION_REGISTRY else (methods[0] if methods else None)
    return {
        "methods": methods,
        "default": default_method,
        "configured": bool(methods and os.environ.get("ENCRYPTION_KEY")),
    }


@router.post("/encryption")
async def process_encryption(
    input_file: UploadFile = File(...),
    subscriber_id_col: str = Form("subscriber_id"),
    encryption_method: str = Form(...),
):
    try:
        input_df = _read_csv(await input_file.read())
    except Exception as exc:
        raise HTTPException(400, f"Could not parse input CSV: {exc}") from exc

    if subscriber_id_col not in input_df.columns:
        raise HTTPException(422, f"Column '{subscriber_id_col}' not found. Available: {list(input_df.columns)}")

    if not ENCRYPTION_REGISTRY:
        raise HTTPException(
            501,
            {
                "message": "No encryption providers are configured.",
                "info": "Implement a provider in app/demask/encryption_provider.py and register it in ENCRYPTION_REGISTRY.",
                "available_methods": [],
            },
        )

    try:
        result = _encryption_provider.process(
            df=input_df, subscriber_id_col=subscriber_id_col, encryption_method=encryption_method
        )
    except NotImplementedError as exc:
        raise HTTPException(501, {"message": str(exc), "available_methods": list(ENCRYPTION_REGISTRY.keys())}) from exc
    except ValueError as exc:
        raise HTTPException(400, {"message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(500, f"Processing error: {exc}") from exc

    headers = {
        "X-Total-Records": str(result.total_records),
        "X-Processed": str(result.processed),
        "X-Unprocessed": str(result.unprocessed),
        "X-Errors": str(result.errors),
        "Access-Control-Expose-Headers": _RESULT_HEADERS_EXPOSE,
    }
    return _csv_response(result.dataframe, "decrypted_subscribers.csv", headers)
