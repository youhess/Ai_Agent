"""Domain configuration: replace this module first when adapting a competition topic."""

BUSINESS_CONFIG = {
    "app_name": "社会治理智能分析平台",
    "agent_name": "社会治理分析助手",
    "domain": "social_governance",
    "description": "面向街道、社区与城市治理工作人员的事件分析 Demo",
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
