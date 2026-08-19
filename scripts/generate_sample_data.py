"""Generate deterministic, patterned fictional data for the competition Demo."""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from database.init_db import init_database  # noqa: E402
from database.repository import replace_cases  # noqa: E402


DISTRICTS = {
    "滨江区": ["长河街道", "西兴街道", "浦沿街道"],
    "上城区": ["湖滨街道", "望江街道", "四季青街道"],
    "拱墅区": ["武林街道", "祥符街道", "半山街道"],
    "西湖区": ["翠苑街道", "古荡街道", "留下街道"],
}
CATEGORIES = ["市容环境", "垃圾堆放", "道路设施", "噪声扰民", "占道经营", "停车问题", "公共设施损坏", "社区服务"]
DESCRIPTIONS = {
    "市容环境": "沿街公共区域存在杂物，影响环境秩序",
    "垃圾堆放": "居民反映生活垃圾未及时清运并出现堆积",
    "道路设施": "道路局部破损，雨天存在积水风险",
    "噪声扰民": "晚间经营及施工噪声影响周边居民休息",
    "占道经营": "流动摊点占用人行通道，影响正常通行",
    "停车问题": "车辆违规停放造成道路通行压力",
    "公共设施损坏": "公共照明及配套设施损坏需要检修",
    "社区服务": "居民提出社区便民服务协调需求",
}
RESPONSIBLE_UNITS = {
    "市容环境": "市容管理模拟组", "垃圾堆放": "环卫处置模拟组", "道路设施": "道路养护模拟组",
    "噪声扰民": "综合协调模拟组", "占道经营": "市容管理模拟组", "停车问题": "交通协调模拟组",
    "公共设施损坏": "设施维护模拟组", "社区服务": "社区服务模拟组",
}


def generate(count: int = 240, seed: int = 2026) -> list[dict]:
    random.seed(seed)
    now = datetime.now().replace(microsecond=0)
    rows = []
    for index in range(count):
        age = random.randint(0, 44)
        district = random.choices(list(DISTRICTS), weights=[34, 24, 22, 20])[0]
        category = random.choice(CATEGORIES)
        # Designed signal: recent Binjiang noise complaints and Changhe waste cases rise sharply.
        if age < 7 and district == "滨江区" and random.random() < 0.56:
            category = "噪声扰民"
        street = random.choice(DISTRICTS[district])
        if age < 14 and district == "滨江区" and random.random() < 0.25:
            street, category = "长河街道", "垃圾堆放"
        hour = random.choices(range(8, 23), weights=[1] * 10 + [3, 4, 5, 4, 3])[0]
        created = now - timedelta(days=age, hours=random.randint(0, 20), minutes=random.randint(0, 59))
        created = created.replace(hour=hour)
        if created > now:
            created -= timedelta(days=1)
        priority = random.choices(["低", "中", "高"], weights=[22, 61, 17])[0]
        if category in {"道路设施", "公共设施损坏"} and random.random() < 0.28:
            priority = "高"
        status = random.choices(["待处理", "处理中", "已完成"], weights=[18, 20, 62])[0]
        resolved = None
        if status == "已完成":
            base_hours = random.randint(8, 55)
            if category == "道路设施":
                base_hours += random.randint(35, 80)  # Designed slower-resolution category.
            resolved_at = min(created + timedelta(hours=base_hours), now)
            resolved = resolved_at.isoformat(timespec="seconds")
        evidence_complete = status == "已完成" and random.random() < 0.88
        if status == "处理中":
            evidence_complete = random.random() < 0.3
        timeline = [{
            "action": "受理登记", "operator_role": "受理员",
            "occurred_at": created.isoformat(timespec="seconds"), "note": "完成事件登记与基础信息核验",
        }]
        if status in {"处理中", "已完成"}:
            assigned_at = min(created + timedelta(minutes=20), now)
            timeline.append({
                "action": "派单签收", "operator_role": "分派员",
                "occurred_at": assigned_at.isoformat(timespec="seconds"), "note": f"已分派至{RESPONSIBLE_UNITS[category]}",
            })
        if status == "处理中":
            handling_at = min(created + timedelta(hours=2), now)
            timeline.append({
                "action": "现场处置", "operator_role": "处置员",
                "occurred_at": handling_at.isoformat(timespec="seconds"), "note": "正在核实并记录处置结果",
            })
        if status == "已完成" and resolved:
            resolved_at = datetime.fromisoformat(resolved)
            timeline.extend([
                {
                    "action": "现场处置", "operator_role": "处置员",
                    "occurred_at": max(created, resolved_at - timedelta(minutes=30)).isoformat(timespec="seconds"),
                    "note": "完成模拟处置并提交结果材料",
                },
                {
                    "action": "复核办结", "operator_role": "复核员",
                    "occurred_at": resolved, "note": "复核处置结果并完成归档",
                },
            ])
        rows.append({
            "id": f"SG-{now:%Y%m}-{index + 1:04d}", "category": category,
            "district": district, "street": street,
            "description": DESCRIPTIONS[category],
            "level": {"高": "一级", "中": "二级", "低": "三级"}[priority], "priority": priority,
            "status": status, "created_at": created.isoformat(timespec="seconds"),
            "responsible_unit": RESPONSIBLE_UNITS[category], "evidence_complete": int(evidence_complete),
            "resolved_at": resolved, "source": random.choice(["12345热线", "网格巡查", "居民上报", "物联感知"]),
            "timeline": timeline,
        })
    # Stabilize the headline signal across environments and execution times.
    current_binjiang = [row for row in rows if row["district"] == "滨江区" and datetime.fromisoformat(row["created_at"]) >= now - timedelta(days=7)]
    previous_binjiang = [row for row in rows if row["district"] == "滨江区" and now - timedelta(days=14) <= datetime.fromisoformat(row["created_at"]) < now - timedelta(days=7)]
    for row in current_binjiang[:8]:
        row["category"] = "噪声扰民"
        row["description"] = DESCRIPTIONS["噪声扰民"]
        row["responsible_unit"] = RESPONSIBLE_UNITS["噪声扰民"]
        for action in row["timeline"]:
            if action["action"] == "派单签收":
                action["note"] = f"已分派至{RESPONSIBLE_UNITS['噪声扰民']}"
    for row in previous_binjiang[:3]:
        row["category"] = "噪声扰民"
        row["description"] = DESCRIPTIONS["噪声扰民"]
        row["responsible_unit"] = RESPONSIBLE_UNITS["噪声扰民"]
        for action in row["timeline"]:
            if action["action"] == "派单签收":
                action["note"] = f"已分派至{RESPONSIBLE_UNITS['噪声扰民']}"
    return rows


if __name__ == "__main__":
    init_database()
    data = generate()
    replace_cases(data)
    print(f"Generated {len(data)} fictional Demo cases.")
