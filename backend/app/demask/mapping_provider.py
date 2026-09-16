"""
Mapping-based subscriber ID processor.
Single Pandas left-merge -- no row-by-row loops.

Ported from chinthakadd7/Demask (backend/providers/mapping_provider.py).
"""

import pandas as pd

from .base import BaseProcessor, ProcessingResult


class MappingProvider(BaseProcessor):
    def process(
        self,
        df: pd.DataFrame,
        mapping_df: pd.DataFrame,
        input_id_col: str,
        mapping_masked_col: str,
        mapping_original_col: str,
    ) -> ProcessingResult:
        total = len(df)

        # Rename mapping columns to align with input for the merge
        m = mapping_df[[mapping_masked_col, mapping_original_col]].copy()
        m = m.rename(columns={mapping_masked_col: input_id_col, mapping_original_col: "__orig__"})

        # Ensure ID columns are treated as strings to avoid dtype mismatch (e.g., numeric phone numbers)
        merged = df.copy()
        merged[input_id_col] = merged[input_id_col].astype(str)
        m[input_id_col] = m[input_id_col].astype(str)

        # Single bulk left-join -- O(n), preserves original row order
        merged = merged.merge(m, on=input_id_col, how="left")

        mapped_mask = merged["__orig__"].notna()
        merged["mapping_status"] = "UNMAPPED"
        merged.loc[mapped_mask, "mapping_status"] = "MAPPED"

        # Replace masked ID with original where a match was found
        merged.loc[mapped_mask, input_id_col] = merged.loc[mapped_mask, "__orig__"].astype(str)
        merged = merged.drop(columns=["__orig__"])

        processed = int(mapped_mask.sum())
        return ProcessingResult(
            dataframe=merged,
            total_records=total,
            processed=processed,
            unprocessed=total - processed,
            errors=0,
        )
