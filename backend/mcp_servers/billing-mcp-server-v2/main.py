"""
billing-mcp-server-v2
---------------------
A standalone MCP server that converts between RM bills and kWh usage and
estimates solar savings. Uses bill.json lookups and hardcoded solar constants.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, TextContent, Tool

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("billing-mcp-server-v2")

PANEL_RATING_KWP = 0.62
EXPORT_RATE_RM_PER_KWH = 0.20


@dataclass(frozen=True)
class BillRecord:
    kwh: float
    bill: float

    @classmethod
    def from_obj(cls, obj: Dict[str, Any]) -> "BillRecord":
        if not isinstance(obj, dict):
            raise ValueError("Bill record must be an object")
        try:
            kwh = float(obj["kwh"])
            bill = float(obj["bill"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Bill record requires numeric 'kwh' and 'bill' fields") from exc
        return cls(kwh=kwh, bill=bill)

    def to_dict(self) -> Dict[str, float]:
        return {"kwh": self.kwh, "bill": self.bill}


class BillTable:
    def __init__(self, records: Iterable[BillRecord]):
        self.records: List[BillRecord] = sorted(records, key=lambda r: r.bill)
        if not self.records:
            raise ValueError("No bill records provided")
        self.min_bill = self.records[0].bill
        self.max_bill = self.records[-1].bill
        self.min_kwh = min(r.kwh for r in self.records)
        self.max_kwh = max(r.kwh for r in self.records)

    def nearest_by_bill(self, rm: float) -> Optional[BillRecord]:
        value = float(rm)
        if value < self.min_bill or value > self.max_bill:
            return None
        return min(self.records, key=lambda rec: abs(rec.bill - value))

    def nearest_by_kwh(self, kwh: float) -> Optional[BillRecord]:
        value = float(kwh)
        if value < self.min_kwh or value > self.max_kwh:
            return None
        return min(self.records, key=lambda rec: abs(rec.kwh - value))


def _candidate_paths() -> List[Path]:
    base = Path(__file__).resolve().parent
    return [
        base / "bill.json",
        base.parent / "bill.json",
        base.parent / "resource" / "bill.json",
        base.parent.parent / "resource" / "bill.json",
        Path("/app/resource/bill.json"),
    ]


def load_bill_table() -> BillTable:
    fallback = [
        {"bill": 60, "kwh": 90},
        {"bill": 80, "kwh": 120},
        {"bill": 100, "kwh": 150},
        {"bill": 120, "kwh": 180},
        {"bill": 150, "kwh": 225},
        {"bill": 180, "kwh": 270},
        {"bill": 220, "kwh": 330},
        {"bill": 260, "kwh": 390},
        {"bill": 320, "kwh": 480},
        {"bill": 400, "kwh": 600},
        {"bill": 480, "kwh": 720},
        {"bill": 550, "kwh": 820},
        {"bill": 650, "kwh": 950},
        {"bill": 750, "kwh": 1080},
    ]
    for path in _candidate_paths():
        try:
            if path.is_file():
                data = json.loads(path.read_text())
                if not isinstance(data, list):
                    raise ValueError("bill.json must be a list of objects")
                logger.info("Loaded bill.json from %s", path)
                return BillTable(BillRecord.from_obj(item) for item in data)
        except Exception as exc:
            logger.warning("Failed to load bill.json from %s: %s", path, exc)
    logger.warning("bill.json not found; using embedded fallback table")
    return BillTable(BillRecord.from_obj(item) for item in fallback)


def format_out_of_scope(kind: str, value: float, table: BillTable) -> List[TextContent]:
    if kind == "bill":
        msg = (
            f"out_of_scope: bill RM {value} is outside supported range "
            f"{table.min_bill} - {table.max_bill}"
        )
    else:
        msg = (
            f"out_of_scope: kWh {value} is outside supported range "
            f"{table.min_kwh} - {table.max_kwh}"
        )
    return [TextContent(type="text", text=msg)]


def format_rm_to_kwh(table: BillTable, rm: float) -> List[TextContent]:
    rec = table.nearest_by_bill(rm)
    if rec is None:
        return format_out_of_scope("bill", rm, table)
    return [
        TextContent(
            type="text",
            text=f"RM {rm:.2f} maps to {rec.kwh:.1f} kWh (nearest bill entry RM {rec.bill:.2f}).",
        )
    ]


def format_kwh_to_rm(table: BillTable, kwh: float) -> List[TextContent]:
    rec = table.nearest_by_kwh(kwh)
    if rec is None:
        return format_out_of_scope("kwh", kwh, table)
    return [
        TextContent(
            type="text",
            text=f"{kwh:.1f} kWh maps to RM {rec.bill:.2f} (nearest usage entry {rec.kwh:.1f} kWh).",
        )
    ]


def format_solar_impact(table: BillTable, rm: float, morning_usage_percentage: float, sunpeak_hour: float) -> List[TextContent]:
    bill_rec = table.nearest_by_bill(rm)
    if bill_rec is None:
        return format_out_of_scope("bill", rm, table)

    total_usage = bill_rec.kwh
    morning_ratio = float(morning_usage_percentage) / 100.0
    if morning_ratio < 0 or morning_ratio > 1:
        return [TextContent(type="text", text="morning_usage_percentage must be between 0 and 100")]
    if sunpeak_hour <= 0:
        return [TextContent(type="text", text="sunpeak_hour must be greater than 0")]

    raw_panel_qty = total_usage / 30.0 / sunpeak_hour / PANEL_RATING_KWP
    panel_qty = math.ceil(raw_panel_qty)
    
    after_solar_usage = total_usage * (1.0 - morning_ratio)

    new_bill_rec = table.nearest_by_kwh(after_solar_usage)
    if new_bill_rec is None:
        return format_out_of_scope("kwh", after_solar_usage, table)

    new_bill = new_bill_rec.bill
    bill_reduction = rm - new_bill

    total_solar_gen = PANEL_RATING_KWP * sunpeak_hour * panel_qty * 30.0
    consumed_solar = total_usage * morning_ratio
    export_generation = max(total_solar_gen - consumed_solar, 0.0)
    export_income = export_generation * EXPORT_RATE_RM_PER_KWH

    total_saving = bill_reduction + export_income
    new_payable = rm - total_saving
    system_kwp = panel_qty * PANEL_RATING_KWP

    lines = [
        f"1. Based on your current bill of RM {rm:.2f}, your estimated monthly usage is {total_usage:.1f} kWh.",
        f"2. We propose a Solar PV System consisting of {panel_qty} panels for your home, translating to a {system_kwp:.2f} kWp system size.",
        f"3. This calculation assumes that {morning_usage_percentage}% of your total usage occurs during the day and will be offset by solar generation.",
        f"4. Your projected monthly bill after solar is RM {new_bill:.2f} (reduced due to self-consumption).",
        f"5. Direct Bill Savings: RM {rm:.2f} - RM {new_bill:.2f} = RM {bill_reduction:.2f}.",
        f"6. Excess solar generation not used during the day will be exported to the grid at the SMP rate of RM 0.20/kWh.",
        f"   Excess Generation Income: ({total_solar_gen:.1f} kWh generated - {consumed_solar:.1f} kWh consumed) * RM 0.20 = RM {export_income:.2f}.",
        f"7. Total Monthly Savings = Bill Savings + Export Income = RM {bill_reduction:.2f} + RM {export_income:.2f} = RM {total_saving:.2f}.",
    ]
    return [TextContent(type="text", text="\n".join(lines))]


server = Server("billing-mcp-server-v2")
bill_table: Optional[BillTable] = None


def get_table() -> BillTable:
    global bill_table
    if bill_table is None:
        bill_table = load_bill_table()
    return bill_table


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="tnb_bill_rm_to_kwh",
            description="Convert RM bill amount to nearest kWh using bill.json.",
            inputSchema={
                "type": "object",
                "properties": {"rm": {"type": "number", "description": "Bill amount in RM"}},
                "required": ["rm"],
            },
        ),
        Tool(
            name="tnb_bill_kwh_to_rm",
            description="Convert kWh to nearest RM bill using bill.json.",
            inputSchema={
                "type": "object",
                "properties": {"kwh": {"type": "number", "description": "Usage in kWh"}},
                "required": ["kwh"],
            },
        ),
        Tool(
            name="calculate_solar_impact",
            description="Estimate solar impact given bill RM, morning usage %, and sunpeak hours.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rm": {"type": "number", "description": "Current monthly bill in RM"},
                    "morning_usage_percentage": {
                        "type": "number",
                        "description": "Percent of usage in the morning (default 30)",
                        "default": 30.0,
                    },
                    "sunpeak_hour": {
                        "type": "number",
                        "description": "Daily sunpeak hours (default 3.4)",
                        "default": 3.4,
                    },
                },
                "required": ["rm"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> List[TextContent]:
    args = arguments or {}
    try:
        table = get_table()
    except Exception as exc:
        return [TextContent(type="text", text=f"Failed to load bill table: {exc}")]

    try:
        if name == "tnb_bill_rm_to_kwh":
            return format_rm_to_kwh(table, float(args.get("rm")))

        if name == "tnb_bill_kwh_to_rm":
            return format_kwh_to_rm(table, float(args.get("kwh")))

        if name == "calculate_solar_impact":
            return format_solar_impact(
                table,
                float(args.get("rm")),
                float(args.get("morning_usage_percentage", 30.0)),
                float(args.get("sunpeak_hour", 3.4)),
            )

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except (TypeError, ValueError) as exc:
        return [TextContent(type="text", text=f"Invalid arguments: {exc}")]
    except Exception as exc:
        logger.exception("Tool execution error")
        return [TextContent(type="text", text=f"Error: {exc}")]


async def main():
    init_opts = InitializationOptions(
        server_name="billing-mcp-server-v2",
        server_version="1.0.0",
        capabilities=ServerCapabilities(),
    )
    async with stdio_server() as (read, write):
        await server.run(read, write, initialization_options=init_opts)


if __name__ == "__main__":
    asyncio.run(main())
