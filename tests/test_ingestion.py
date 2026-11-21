"""
tests/test_ingestion.py
─────────────────────────────────────────────────────────────────────────────
Tests for data/ingestion.py — the data collection layer.

Coverage:
  • Synthetic generator: transaction count, CSV schema, label file creation,
    sybil/human label presence, no duplicate hashes, address format.
  • _validate_alchemy_key: blank / placeholder / valid keys.
  • CSV schema matches expected fieldnames.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import csv
import sys
import time
import tempfile
import pytest
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_FIELDNAMES = ["hash", "blockNumber", "timeStamp", "from", "to", "value", "gas", "gasPrice"]


@pytest.fixture()
def isolated_tmp(tmp_path, monkeypatch):
    """Redirect RAW_DATA_PATH to tmp_path for each test.

    ingestion.py imports RAW_DATA_PATH as a module-level name, so we must
    patch both the settings module *and* the already-imported binding inside
    data.ingestion.
    """
    import config.settings as settings
    import data.ingestion as ingestion

    raw_dir  = tmp_path / "raw"
    raw_dir.mkdir()
    raw_csv  = raw_dir / "transactions.csv"

    monkeypatch.setattr(settings,  "RAW_DATA_PATH", str(raw_csv))
    monkeypatch.setattr(ingestion, "RAW_DATA_PATH", str(raw_csv))
    return tmp_path, raw_csv


# ─────────────────────────────────────────────────────────────────────────────
#  Alchemy key validation
# ─────────────────────────────────────────────────────────────────────────────

class TestAlchemyKeyValidation:
    def test_blank_key_is_invalid(self):
        from data.ingestion import _validate_alchemy_key
        assert not _validate_alchemy_key("")

    def test_whitespace_key_is_invalid(self):
        from data.ingestion import _validate_alchemy_key
        assert not _validate_alchemy_key("   ")

    def test_placeholder_key_is_invalid(self):
        from data.ingestion import _validate_alchemy_key
        assert not _validate_alchemy_key("your_alchemy_api_key_here")

    def test_real_looking_key_passes(self):
        from data.ingestion import _validate_alchemy_key
        assert _validate_alchemy_key("AbCdEf123456_xKpQr")


# ─────────────────────────────────────────────────────────────────────────────
#  Synthetic data generator
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticDataGenerator:
    N_SMALL = 1_000

    def test_csv_is_created(self, isolated_tmp):
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        assert raw_csv.exists(), "transactions.csv was not created"

    def test_csv_row_count(self, isolated_tmp):
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df = pd.read_csv(raw_csv)
        assert len(df) == self.N_SMALL

    def test_csv_schema(self, isolated_tmp):
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df = pd.read_csv(raw_csv)
        for col in EXPECTED_FIELDNAMES:
            assert col in df.columns, f"Missing column: {col}"

    def test_no_duplicate_hashes(self, isolated_tmp):
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df = pd.read_csv(raw_csv)
        assert df["hash"].nunique() == len(df), "Duplicate tx hashes found"

    def test_no_self_loops_in_honest_txs(self, isolated_tmp):
        """No transaction where from == to (which would be meaningless)."""
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df = pd.read_csv(raw_csv)
        # Honest txs are filtered; bot patterns may technically share,
        # but the generator explicitly prevents self-loops in honest section.
        honest_mask = df["from"].str.startswith("0xaa") & df["to"].str.startswith("0xaa")
        honest = df[honest_mask]
        assert (honest["from"] != honest["to"]).all()

    def test_address_format(self, isolated_tmp):
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df = pd.read_csv(raw_csv)
        for col in ("from", "to"):
            assert df[col].str.startswith("0x").all(), f"Addresses in '{col}' don't start with 0x"
            # Synthetic addresses: 0x + prefix(2) + UUID hex(up to 38) = 36–42 chars
            assert (df[col].str.len() >= 34).all(), f"Addresses in '{col}' are suspiciously short"

    def test_labels_csv_created(self, isolated_tmp):
        tmp_path, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        labels_path = raw_csv.parent / "labels.csv"
        assert labels_path.exists(), "labels.csv was not created"

    def test_labels_csv_has_sybil_and_human(self, isolated_tmp):
        tmp_path, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df_labels = pd.read_csv(raw_csv.parent / "labels.csv")
        assert set(df_labels["is_sybil"].unique()) == {0, 1}, \
            "labels.csv should contain both 0 (Human) and 1 (Sybil)"

    def test_labels_cover_all_addresses_in_csv(self, isolated_tmp):
        tmp_path, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df_txs    = pd.read_csv(raw_csv)
        df_labels = pd.read_csv(raw_csv.parent / "labels.csv")
        all_addrs = set(df_txs["from"]) | set(df_txs["to"])
        labeled   = set(df_labels["address"])
        unlabeled = all_addrs - labeled
        assert not unlabeled, f"{len(unlabeled)} addresses have no label"

    def test_value_and_gas_are_numeric_strings(self, isolated_tmp):
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df = pd.read_csv(raw_csv)
        pd.to_numeric(df["value"], errors="raise")
        pd.to_numeric(df["gas"],   errors="raise")

    def test_sybil_prefix_pattern_b0_in_botfarm(self, isolated_tmp):
        """At least some 0xb0… addresses (bot-farm controllers) appear in txs."""
        _, raw_csv = isolated_tmp
        from data.ingestion import generate_sybil_synthetic_data
        generate_sybil_synthetic_data(self.N_SMALL)
        df = pd.read_csv(raw_csv)
        has_b0 = (
            df["from"].str.startswith("0xb0") |
            df["to"].str.startswith("0xb0")
        ).any()
        assert has_b0, "Expected bot-farm controller addresses (0xb0…) in dataset"
