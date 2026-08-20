"""Domain configuration: replace this module first when adapting a competition topic."""

BUSINESS_CONFIG = {
    "app_name": "基层治理协同处置平台",
    "agent_name": "基层治理协同智能体",
    "domain": "social_governance",
    "description": "面向街道、社区与协同单位的治理事件研判、派单、复核与办结 Demo",
    "entity_name": "治理事件",
    "knowledge_directory": "knowledge",
    "categories": [
        "市容环境", "垃圾堆放", "道路设施", "噪声扰民",
        "占道经营", "停车问题", "公共设施损坏", "社区服务",
    ],
    "dashboard": {
        "metrics": ["total_cases", "today_cases", "pending_cases", "high_risk_cases", "completion_rate"]
    },
}
