from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from config import get_settings
from database.admin_repository import (
    create_dataset_import,
    get_dataset_import,
    replace_cases_from_import,
)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_ROWS = 50_000

FIELD_ALIASES = {
    "事件id": "id", "事件ID": "id", "id": "id", "ID": "id", "编号": "id",
    "区域": "district", "区县": "district", "district": "district",
    "类型": "category", "事件类型": "category", "category": "category",
    "事件描述": "description", "描述": "description", "description": "description",
    "上报时间": "created_at", "创建时间": "created_at", "created_at": "created_at",
    "街道": "street", "street": "street",
    "等级": "level", "level": "level",
    "优先级": "priority", "priority": "priority",
    "状态": "status", "status": "status",
    "责任单位": "responsible_unit", "responsible_unit": "responsible_unit",
    "证据状态": "evidence_complete", "证据完整": "evidence_complete", "evidence_complete": "evidence_complete",
    "办结时间": "resolved_at", "resolved_at": "resolved_at",
    "来源": "source", "source": "source",
}
REQUIRED_FIELDS = {"id", "district", "category", "description", "created_at"}
DEFAULTS = {
    "street": "未提供", "level": "三级", "priority": "中", "status": "待处理",
    "responsible_unit": "待分派单位", "evidence_complete": "否", "resolved_at": "", "source": "批量导入",
}
ENUMS = {
    "level": {"一级", "二级", "三级"},
    "priority": {"低", "中", "高"},
    "status": {"待处理", "处理中", "已完成"},
}


class ImportValidationError(ValueError):
    pass


def _read_table(file_name: str, content: bytes) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".xlsx":
        return pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ImportValidationError("CSV 编码无法识别，请使用 UTF-8 或 GB18030")
    raise ImportValidationError("仅支持 .xlsx 和 .csv 文件")


def _normalize_date(value: str, *, field: str, row_number: int, errors: list[dict[str, Any]]) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = pd.to_datetime(value, errors="raise")
        return parsed.to_pydatetime().isoformat(timespec="seconds")
    except (ValueError, TypeError, OverflowError):
        errors.append({"row": row_number, "field": field, "message": f"无法解析日期：{value}"})
        return None


def _evidence_value(value: str, row_number: int, errors: list[dict[str, Any]]) -> int:
    normalized = value.strip().lower()
    if normalized in {"是", "完整", "已完整", "1", "true", "yes", "y"}:
        return 1
    if normalized in {"否", "不完整", "待补充", "0", "false", "no", "n", ""}:
        return 0
    errors.append({"row": row_number, "field": "evidence_complete", "message": f"无法识别证据状态：{value}"})
    return 0


def preview_import(file_name: str, content: bytes) -> dict[str, Any]:
    safe_name = Path(file_name or "dataset").name
    if not content:
        raise ImportValidationError("上传文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImportValidationError("文件不能超过 20 MB")
    frame = _read_table(safe_name, content)
    if len(frame.index) > MAX_ROWS:
        raise ImportValidationError("单次最多导入 50,000 条记录")

    recognized: dict[str, str] = {}
    for original in frame.columns:
        normalized_header = str(original).strip()
        mapped = FIELD_ALIASES.get(normalized_header) or FIELD_ALIASES.get(normalized_header.lower())
        if mapped and mapped not in recognized.values():
            recognized[original] = mapped
    frame = frame.rename(columns=recognized)
    missing = sorted(REQUIRED_FIELDS - set(frame.columns))
    if missing:
        labels = {"id": "事件 ID", "district": "区域", "category": "类型", "description": "事件描述", "created_at": "上报时间"}
        raise ImportValidationError("缺少必填字段：" + "、".join(labels[item] for item in missing))

    warnings = [f"未提供“{field}”，将使用默认值“{value or '空'}”" for field, value in DEFAULTS.items() if field not in frame.columns]
    errors: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    if frame.empty:
        errors.append({"row": 1, "field": "file", "message": "文件中没有可导入的数据行"})
    for index, raw in frame.iterrows():
        row_number = index + 2
        row = {}
        for field in REQUIRED_FIELDS | set(DEFAULTS):
            value = str(raw.get(field, "")).strip()
            row[field] = value if value or field in REQUIRED_FIELDS else DEFAULTS[field]
        for field in REQUIRED_FIELDS:
            if not row[field]:
                errors.append({"row": row_number, "field": field, "message": "必填字段不能为空"})
        if row["id"] in seen_ids:
            errors.append({"row": row_number, "field": "id", "message": f"事件 ID 重复：{row['id']}"})
        seen_ids.add(row["id"])
        for field, allowed in ENUMS.items():
            if row[field] not in allowed:
                errors.append({"row": row_number, "field": field, "message": f"非法值“{row[field]}”，可选：{'、'.join(sorted(allowed))}"})
        created_at = _normalize_date(row["created_at"], field="created_at", row_number=row_number, errors=errors)
        resolved_at = _normalize_date(row["resolved_at"], field="resolved_at", row_number=row_number, errors=errors)
        rows.append({
            "id": row["id"], "category": row["category"], "district": row["district"],
            "street": row["street"], "description": row["description"], "level": row["level"],
            "priority": row["priority"], "status": row["status"], "responsible_unit": row["responsible_unit"],
            "evidence_complete": _evidence_value(row["evidence_complete"], row_number, errors),
            "created_at": created_at or row["created_at"], "resolved_at": resolved_at, "source": row["source"],
        })

    import_id = uuid.uuid4().hex
    import_dir = get_settings().imports_dir
    import_dir.mkdir(parents=True, exist_ok=True)
    raw_path = import_dir / f"{import_id}{Path(safe_name).suffix.lower()}"
    normalized_path = import_dir / f"{import_id}.normalized.json"
    raw_path.write_bytes(content)
    normalized_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    status = "invalid" if errors else "validated"
    create_dataset_import({
        "id": import_id, "file_name": safe_name, "stored_path": str(raw_path), "size_bytes": len(content),
        "status": status, "row_count": len(rows), "error_count": len(errors),
        "errors": errors[:200], "warnings": warnings,
    })
    return {
        "import_id": import_id, "file_name": safe_name, "status": status, "row_count": len(rows),
        "recognized_fields": sorted(set(recognized.values())), "errors": errors[:200], "error_count": len(errors),
        "warnings": warnings, "preview": rows[:20], "can_commit": not errors and bool(rows),
    }


def commit_import(import_id: str) -> dict[str, Any]:
    record = get_dataset_import(import_id)
    if not record:
        raise ImportValidationError("导入预检记录不存在")
    if record["status"] == "committed":
        raise ImportValidationError("该数据集已经导入")
    if record["status"] != "validated" or record["error_count"]:
        raise ImportValidationError("数据仍有校验错误，不能替换当前数据集")
    if record["row_count"] < 1:
        raise ImportValidationError("数据集中没有可导入记录")
    raw_path = Path(record["stored_path"])
    normalized_path = raw_path.with_name(f"{import_id}.normalized.json")
    if not normalized_path.exists():
        raise ImportValidationError("预检数据已失效，请重新上传")
    rows = json.loads(normalized_path.read_text(encoding="utf-8"))
    replace_cases_from_import(import_id, rows)
    return {"import_id": import_id, "status": "committed", "row_count": len(rows), "file_name": record["file_name"]}


def template_bytes() -> bytes:
    sample = pd.DataFrame([{
        "事件ID": "CASE-001", "区域": "滨江区", "类型": "道路设施", "事件描述": "道路局部破损",
        "上报时间": "2026-08-19 09:00:00", "街道": "长河街道", "等级": "二级", "优先级": "高",
        "状态": "待处理", "责任单位": "城市管理部门", "证据状态": "否", "办结时间": "", "来源": "热线平台",
    }])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sample.to_excel(writer, index=False, sheet_name="治理事件")
    return buffer.getvalue()
