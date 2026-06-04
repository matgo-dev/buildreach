"""信用评估服务层(§三 抽象设计)。

模块组织:
- data_source/  数据源抽象 + Mock 实现
- evaluators.py  规则求值函数集中地(~35 个)
- scoring_engine.py  评分引擎(主入口 compute)
- ai_summary_generator.py  AI 综合评价
- types.py  Pydantic 类型(DataSource 返回 / 引擎输入输出)
- errors.py  自定义异常
"""
