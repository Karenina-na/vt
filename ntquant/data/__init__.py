"""Data layer: catalog, synthetic generation, schema, sources, and ingestion."""
from ntquant.data.catalog import DataCatalog
from ntquant.data.ingest import ingest
from ntquant.data.loaders import get_source
from ntquant.data.schema import normalize_ohlcv_frame
from ntquant.data.synthetic import generate_synthetic_bars

__all__ = [
    "DataCatalog",
    "generate_synthetic_bars",
    "normalize_ohlcv_frame",
    "get_source",
    "ingest",
]
