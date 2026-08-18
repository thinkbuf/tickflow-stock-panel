"""lots 一致性: sync_lot 锁 + 校验先行 + 原子写 的持久化测试。

存储函数均接收 data_dir 参数 → 直接传 tmp_path 隔离 (与 test_strategy_monitor_events 同款)。
sync_lot 需要 fake request: app.state.monitor_engine (stub 记录 set_rules 次数) +
app.state.repo (store.data_dir + resolve_asset_type)。不触网、不建真实 DataStore。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import lots
from app.strategy import monitor_rules


# ── fake request / 引擎 stub ─────────────────────────────
class _StubEngine:
    def __init__(self) -> None:
        self.set_calls = 0
        self.rules = []

    def set_rules(self, rules: list[dict]) -> None:
        self.set_calls += 1
        self.rules = rules


def _make_request(tmp_path: Path, engine: _StubEngine) -> SimpleNamespace:
    repo = SimpleNamespace(
        store=SimpleNamespace(data_dir=tmp_path),
        resolve_asset_type=lambda _symbol: "stock",
    )
    state = SimpleNamespace(monitor_engine=engine, repo=repo)
    return SimpleNamespace(app=SimpleNamespace(state=state))


def _make_lot(**overrides: object) -> dict:
    lot = {
        "id": "lot_test1",
        "symbol": "600519.SH",
        "qty": 100,
        "cost_price": 1500.0,
        "buy_date": "2026-08-01",
        "target_pct": 10,
        "stop_pct": 5,
        "remind_date": "2026-09-01",
        "lead_days": 2,
    }
    lot.update(overrides)
    return lot


def _lot_path(tmp_path: Path, lot_id: str) -> Path:
    return tmp_path / "user_data" / "lots" / f"{lot_id}.json"


def _mock_default_channels(monkeypatch) -> None:
    monkeypatch.setattr("app.services.preferences.get_webhook_default_channels", lambda: [])


# ── 校验先行: validate 失败不留半成品 ────────────────────
def test_sync_lot_validates_before_write(tmp_path, monkeypatch):
    engine = _StubEngine()
    request = _make_request(tmp_path, engine)
    _mock_default_channels(monkeypatch)

    def boom(_rule: dict) -> None:
        raise ValueError("bad rule")

    monkeypatch.setattr("app.strategy.monitor_rules.validate", boom)

    with pytest.raises(HTTPException) as ei:
        lots.sync_lot(request, _make_lot())
    assert ei.value.status_code == 400

    # 批次文件、两条规则文件、引擎重载 全都不该发生
    assert not _lot_path(tmp_path, "lot_test1").exists()
    rules_dir = tmp_path / "user_data" / "monitor_rules"
    assert not rules_dir.exists() or list(rules_dir.glob("*.json")) == []
    assert engine.set_calls == 0


# ── 正常同步: 写批次 + 两条规则 + 单次重载 ───────────────
def test_sync_lot_writes_lot_rules_and_reloads_once(tmp_path, monkeypatch):
    engine = _StubEngine()
    request = _make_request(tmp_path, engine)
    _mock_default_channels(monkeypatch)

    lots.sync_lot(request, _make_lot())

    assert _lot_path(tmp_path, "lot_test1").exists()
    price = monitor_rules.load_one(tmp_path, "lot_test1_p")
    date_rule = monitor_rules.load_one(tmp_path, "lot_test1_d")
    assert price is not None
    assert price["conditions"] == [
        {"field": "close", "op": ">=", "value": 1650.0},  # 1500 × 1.10
        {"field": "close", "op": "<=", "value": 1425.0},  # 1500 × 0.95
    ]
    assert date_rule is not None and date_rule["remind_date"] == "2026-09-01"
    assert engine.set_calls == 1


# ── 并发同一批次: 锁内保持 批次↔规则 一致 ─────────────────
def test_sync_lot_concurrent_same_lot_keeps_consistent(tmp_path, monkeypatch):
    engine = _StubEngine()
    request = _make_request(tmp_path, engine)
    _mock_default_channels(monkeypatch)

    def worker(i: int) -> None:
        lots.sync_lot(request, _make_lot(target_pct=10 + i))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(worker, range(8)))

    # 只该剩一个批次, 且落盘规则必须与该批次当前值一致 (无跨请求混写)
    rows = lots.load_all(tmp_path)
    assert len(rows) == 1
    final = rows[0]
    price, _date_rule = lots.lot_to_rules(final)
    assert price is not None
    stored_price = monitor_rules.load_one(tmp_path, f"{final['id']}_p")
    assert stored_price is not None
    assert stored_price["conditions"] == price["conditions"]


# ── 删除: 批次 + 两条规则 + 重载 ─────────────────────────
def test_delete_lot_removes_lot_and_rules_and_reloads(tmp_path, monkeypatch):
    engine = _StubEngine()
    request = _make_request(tmp_path, engine)
    _mock_default_channels(monkeypatch)

    lots.sync_lot(request, _make_lot())
    before = engine.set_calls
    lots.delete_lot("lot_test1", request)

    assert not _lot_path(tmp_path, "lot_test1").exists()
    assert monitor_rules.load_one(tmp_path, "lot_test1_p") is None
    assert monitor_rules.load_one(tmp_path, "lot_test1_d") is None
    assert engine.set_calls == before + 1


# ── 原子写: 立即可完整读回, 目录无残留 .tmp ──────────────
def test_save_one_atomic_leaves_no_tmp(tmp_path):
    lots.save_one(tmp_path, _make_lot())
    assert lots.load_all(tmp_path)[0]["id"] == "lot_test1"
    lots_dir = tmp_path / "user_data" / "lots"
    assert [f for f in lots_dir.iterdir() if f.suffix == ".tmp"] == []


def test_monitor_rule_save_one_atomic(tmp_path):
    rule = monitor_rules.normalize({
        "id": "mr_x",
        "name": "x",
        "type": "price",
        "scope": "symbols",
        "symbols": ["600519.SH"],
        "conditions": [{"field": "close", "op": ">=", "value": 100.0}],
    })
    monitor_rules.save_one(tmp_path, rule)
    loaded = monitor_rules.load_one(tmp_path, "mr_x")
    assert loaded is not None and loaded["id"] == "mr_x"
    rules_dir = tmp_path / "user_data" / "monitor_rules"
    assert [f for f in rules_dir.iterdir() if f.suffix == ".tmp"] == []


# ── 结构化校验错误: 400 detail 带 field, 供前端逐字段高亮 ──
@pytest.mark.parametrize("overrides, expected_field", [
    ({"symbol": " "}, "symbol"),
    ({"cost_price": 0}, "cost_price"),
    ({"qty": -1}, "qty"),
    ({"target_pct": -1}, "target_pct"),
    ({"stop_pct": -1}, "stop_pct"),
    ({"lead_days": -1}, "lead_days"),
    ({"remind_date": "2026/09/01"}, "remind_date"),
    ({"buy_date": "bad"}, "buy_date"),
    ({"target_pct": 0, "stop_pct": 0, "remind_date": None}, "monitor_point"),
])
def test_upsert_lot_returns_structured_field_errors(tmp_path, overrides, expected_field):
    request = _make_request(tmp_path, _StubEngine())
    lot = _make_lot(**overrides)
    with pytest.raises(HTTPException) as ei:
        lots.upsert_lot(lots.LotModel(**lot), request)
    assert ei.value.status_code == 400
    detail = ei.value.detail
    assert isinstance(detail, dict) and detail["field"] == expected_field
    assert detail["message"]
