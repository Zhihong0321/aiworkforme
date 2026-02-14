"""
BillTable MCP helper
--------------------
Loads bill data from bill.json and exposes nearest_by_bill / nearest_by_kwh helpers.

Search order for bill.json:
1) Current directory (next to this file)
2) Parent directory
3) ../resource/ relative to this file
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
  from mcp.server import Server
  from mcp.server.stdio import stdio_server
  from mcp.types import TextContent, Tool
except ImportError as exc:
  sys.stderr.write(
    "The 'mcp' package is required to run this MCP server. "
    "Install with `pip install mcp` inside the server environment. "
    f"ImportError: {exc}\n"
  )
  raise


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
  def __init__(self, records: Optional[Iterable[BillRecord]] = None) -> None:
    self.source_path: Optional[Path] = None
    if records is None:
      records = self._load_from_disk()
    self.records: List[BillRecord] = list(records)
    if not self.records:
      raise ValueError("No bill records loaded")
    # Pre-sort for bounds and nearest lookups.
    self._by_bill = sorted(self.records, key=lambda r: r.bill)
    self._by_kwh = sorted(self.records, key=lambda r: r.kwh)

  def nearest_by_bill(self, rm: float) -> Dict[str, float]:
    """
    Return the record whose bill value is closest to the given RM.
    Out-of-range values return the min or max record.
    """
    value = float(rm)
    return self._nearest(value, key=lambda r: r.bill, sorted_list=self._by_bill)

  def nearest_by_kwh(self, kwh: float) -> Dict[str, float]:
    """
    Return the record whose kWh value is closest to the given kWh.
    Out-of-range values return the min or max record.
    """
    value = float(kwh)
    return self._nearest(value, key=lambda r: r.kwh, sorted_list=self._by_kwh)

  def _nearest(self, value: float, key, sorted_list: List[BillRecord]) -> Dict[str, float]:
    # Bounds guard.
    min_rec = sorted_list[0]
    max_rec = sorted_list[-1]
    if value <= key(min_rec):
      return min_rec.to_dict()
    if value >= key(max_rec):
      return max_rec.to_dict()
    # Nearest by absolute difference.
    best = min(sorted_list, key=lambda rec: abs(key(rec) - value))
    return best.to_dict()

  def _load_from_disk(self) -> List[BillRecord]:
    base = Path(__file__).resolve().parent
    candidates = [
      base / "bill.json",
      base.parent / "bill.json",
      base.parent / "resource" / "bill.json",
    ]
    for path in candidates:
      if path.is_file():
        self.source_path = path
        data = json.loads(path.read_text())
        if not isinstance(data, list):
          raise ValueError("bill.json must be a list of objects")
        return [BillRecord.from_obj(item) for item in data]
    raise FileNotFoundError(
      "bill.json not found in current directory, parent directory, or ../resource/"
    )


server = Server("tnb-bill-mapper")
bill_table: Optional[BillTable] = None


def get_table() -> BillTable:
  global bill_table
  if bill_table is None:
    bill_table = BillTable()
  return bill_table


@server.list_tools()
async def list_tools() -> List[Tool]:
  return [
    Tool(
      name="tnb_bill_rm_to_kwh",
      description="Convert RM bill amount to nearest kWh using bill.json.",
      inputSchema={
        "type": "object",
        "properties": {
          "rm": {"type": "number", "description": "Bill amount in RM"}
        },
        "required": ["rm"],
      },
    ),
    Tool(
      name="tnb_bill_kwh_to_rm",
      description="Convert kWh to nearest RM bill using bill.json.",
      inputSchema={
        "type": "object",
        "properties": {
          "kwh": {"type": "number", "description": "Usage in kWh"}
        },
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
  except Exception as exc:  # pragma: no cover - defensive for runtime env issues
    return [TextContent(type="text", text=f"Failed to load bill.json: {exc}")]

  try:
    if name == "tnb_bill_rm_to_kwh":
      if "rm" not in args:
        return [TextContent(type="text", text="Missing required argument: rm")]
      rm_val = float(args.get("rm"))
      rec = table.nearest_by_bill(rm_val)
      return [
        TextContent(
          type="text",
          text=f"RM {rm_val} maps to {rec['kwh']} kWh (nearest bill entry RM {rec['bill']})",
        )
      ]

    if name == "tnb_bill_kwh_to_rm":
      if "kwh" not in args:
        return [TextContent(type="text", text="Missing required argument: kwh")]
      kwh_val = float(args.get("kwh"))
      rec = table.nearest_by_kwh(kwh_val)
      return [
        TextContent(
          type="text",
          text=f"{rec['kwh']} kWh maps to RM {rec['bill']} (nearest to requested {kwh_val} kWh)",
        )
      ]

    if name == "calculate_solar_impact":
      if "rm" not in args:
        return [TextContent(type="text", text="Missing required argument: rm")]
      rm_val = float(args.get("rm"))
      morning_pct = float(args.get("morning_usage_percentage", 30.0))
      sunpeak_hour = float(args.get("sunpeak_hour", 3.4))

      total_usage = table.nearest_by_bill(rm_val)
      total_usage_kwh = total_usage["kwh"]

      panel_rating = 0.62
      panel_qty = total_usage_kwh / 30.0 / sunpeak_hour / panel_rating

      after_solar_usage = total_usage_kwh * (1.0 - (morning_pct / 100.0))

      new_bill = table.nearest_by_kwh(after_solar_usage)
      new_bill_rm = new_bill["bill"]

      bill_reduction = rm_val - new_bill_rm

      solar_gen_monthly = panel_rating * sunpeak_hour * panel_qty * 30.0

      exported_energy = solar_gen_monthly - (total_usage_kwh * morning_pct / 100.0)

      export_income = exported_energy * 0.20

      total_saving = bill_reduction + export_income

      new_payable = rm_val - total_saving

      lines = [
        "Solar Impact Estimation",
        f"Input Bill (RM): {rm_val:.2f}",
        f"System Size (estimated panels): {panel_qty:.2f}",
        f"Bill Reduction (RM): {bill_reduction:.2f}",
        f"Export Income (RM): {export_income:.2f}",
        f"Total Saving (RM): {total_saving:.2f}",
        f"New Payable (RM): {new_payable:.2f}",
      ]
      return [TextContent(type="text", text="\n".join(lines))]

    return [TextContent(type="text", text=f"Tool '{name}' not found.")]

  except Exception as exc:
    return [TextContent(type="text", text=f"Error executing {name}: {exc}")]


async def main() -> None:
  async with stdio_server() as (reader, writer):
    await server.run(reader, writer)


if __name__ == "__main__":
  asyncio.run(main())
