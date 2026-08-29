"""Data layer: catalog, synthetic generation, and external loaders."""
from ntquant.data.catalog import DataCatalog
from ntquant.data.synthetic import generate_synthetic_bars

__all__ = ["DataCatalog", "generate_synthetic_bars"]
