"""
Demask -- batch-convert masked subscriber IDs back to originals, via a
CSV mapping lookup or a pluggable decryption provider.

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


@router.post("/mapping")
async def process_mapping(
    input_file: UploadFile = File(...),
    mapping_file: UploadFile = File(...),
    input_id_col: str = Form("subscriber_id"),
    mapping_masked_col: str = Form("masked_subscriber_id"),
    mapping_original_col: str = Form("original_subscriber_id"),
):
    # Read CSVs as strings to preserve phone numbers and prevent dtype mismatch
    try:
        input_df = pd.read_csv(io.BytesIO(await input_file.read()), dtype=str)
    except Exception as exc:
        raise HTTPException(400, f"Could not parse input CSV: {exc}") from exc

    try:
        mapping_df = pd.read_csv(io.BytesIO(await mapping_file.read()), dtype=str)
    except Exception as exc:
        raise HTTPException(400, f"Could not parse mapping CSV: {exc}") from exc

    if input_id_col not in input_df.columns:
        raise HTTPException(422, f"Column '{input_id_col}' not found in input CSV. Available: {list(input_df.columns)}")
    if mapping_masked_col not in mapping_df.columns:
        raise HTTPException(422, f"Column '{mapping_masked_col}' not found in mapping CSV. Available: {list(mapping_df.columns)}")
    if mapping_original_col not in mapping_df.columns:
        raise HTTPException(422, f"Column '{mapping_original_col}' not found in mapping CSV. Available: {list(mapping_df.columns)}")

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

    buf = io.StringIO()
    result.dataframe.to_csv(buf, index=False)
    csv_bytes = buf.getvalue().encode("utf-8")

    headers = {
        "X-Total-Records": str(result.total_records),
        "X-Processed": str(result.processed),
        "X-Unprocessed": str(result.unprocessed),
        "X-Errors": str(result.errors),
        "Content-Disposition": 'attachment; filename="updated_subscribers.csv"',
        "Access-Control-Expose-Headers": _RESULT_HEADERS_EXPOSE,
    }
    return StreamingResponse(iter([csv_bytes]), media_type="text/csv", headers=headers)


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
        input_df = pd.read_csv(io.BytesIO(await input_file.read()), dtype=str)
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

    buf = io.StringIO()
    result.dataframe.to_csv(buf, index=False)
    csv_bytes = buf.getvalue().encode("utf-8")

    headers = {
        "X-Total-Records": str(result.total_records),
        "X-Processed": str(result.processed),
        "X-Unprocessed": str(result.unprocessed),
        "X-Errors": str(result.errors),
        "Content-Disposition": 'attachment; filename="decrypted_subscribers.csv"',
        "Access-Control-Expose-Headers": _RESULT_HEADERS_EXPOSE,
    }
    return StreamingResponse(iter([csv_bytes]), media_type="text/csv", headers=headers)
