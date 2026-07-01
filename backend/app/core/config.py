"""全局配置:从 .env 读取,Pydantic 校验后注入。"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 数据库 — PostgreSQL(本机 brew @16,端口 5433 以避开 EnterpriseDB pg13)
    DATABASE_URL: str = "postgresql+asyncpg://liujingjing@localhost:5433/overseas_supply_dev"

    # 数据库连接池（生产环境调优）
    DB_POOL_SIZE: int = 20              # 连接池大小
    DB_MAX_OVERFLOW: int = 10           # 峰值额外连接数
    DB_POOL_TIMEOUT: int = 30           # 获取连接超时(秒)
    DB_POOL_RECYCLE: int = 3600         # 连接回收时间(秒)

    # JWT
    JWT_SECRET_KEY: str = Field(..., min_length=16)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Super admin 种子(始终种入,生产唯一保留)
    SUPER_ADMIN_EMAIL: str = "superadmin@platform.local"
    SUPER_ADMIN_INITIAL_PASSWORD: str = "Aa123456789"

    # demo seed 开关:控制是否种入中建三局 BuyerOrg 与 admin/operator/buyer demo 账号
    # 本地开发推荐 true;**生产部署务必 false**
    SEED_DEMO_ACCOUNTS: bool = False

    # 日志
    LOG_LEVEL: str = "INFO"

    # ---- LLM(信用评估 AI 综合评价 + 对话追问)----
    # DashScope OpenAI 兼容端点 + openai SDK 调用(便于后续切其他国产模型)
    # 真实密钥**绝不**进 Git;ECS 上由 .env.production 注入
    DASHSCOPE_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_CHAT_MODEL: str = "qwen-plus"
    QWEN_CHAT_TEMPERATURE: float = 0.2
    QWEN_TIMEOUT_SECONDS: float = 30.0

    # ---- Tavily 搜索 API(Δ7 柬埔寨公开数据源抓取)----
    # 真实 key 绝不进 Git;本地 .env / ECS .env.production 注入
    TAVILY_API_KEY: str = ""
    TAVILY_API_URL: str = "https://api.tavily.com"
    TAVILY_TIMEOUT_SECONDS: int = 15
    TAVILY_MAX_RESULTS_PER_QUERY: int = 5

    # ---- 抓取缓存与限速(Δ7)----
    CREDIT_HARVEST_CACHE_TTL_HOURS: int = 24
    CREDIT_HARVEST_TAVILY_CALLS_PER_HARVEST: int = 10  # 单家公司单次抓取 Tavily 调用上限
    CREDIT_HARVEST_LLM_TIMEOUT_SECONDS: int = 30
    CREDIT_HARVEST_LLM_RETRY: int = 1

    # ---- Δ7 v0.3:源字段追溯 + 白名单搜索 ----
    CREDIT_HARVEST_EVIDENCE_FUZZY_THRESHOLD: float = 0.3  # quote 与来源 content 匹配度下限
    CREDIT_HARVEST_WHITELIST_FALLBACK_THRESHOLD: int = 3  # 白名单结果少于此值触发全网兜底

    # ---- 翻译(i18n)----
    # aliyun / google / mock / none;缺凭据时自动降级为 none
    TRANSLATION_PROVIDER: str = "google"
    # Google Cloud Translation v2 Basic (API Key)
    GOOGLE_TRANSLATE_API_KEY: str = ""
    GOOGLE_TRANSLATE_TIMEOUT_SECONDS: float = 10.0
    # 阿里云机器翻译
    ALIYUN_TRANSLATE_ACCESS_KEY_ID: str = ""
    ALIYUN_TRANSLATE_ACCESS_KEY_SECRET: str = ""
    ALIYUN_TRANSLATE_REGION: str = "cn-hangzhou"
    ALIYUN_TRANSLATE_TIMEOUT_SECONDS: float = 10.0

    # ---- i18n 自动补译 ----
    I18N_AUTO_TRANSLATE_ENABLED: bool = True       # 总开关
    I18N_SWEEP_INTERVAL_SECONDS: int = 300          # 调度扫描周期(5 分钟)
    I18N_SWEEP_BATCH_LIMIT: int = 100              # 每批提交行数(翻完即 commit,循环取下一批)

    # CORS(逗号分隔,运行时拆为列表)
    CORS_ORIGINS_RAW: str = Field(
        default="http://localhost:3000", alias="CORS_ORIGINS"
    )

    # 登录限流(MVP 单机内存)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_MAX_FAILURES: int = 5
    LOGIN_RATE_LIMIT_LOCK_SECONDS: int = 300

    # 图片静态文件前缀（相对路径，前端用 API_BASE_URL 拼完整地址）
    IMAGE_PATH_PREFIX: str = "/static"
    IMAGE_MAX_PIXELS: int = 25_000_000
    IMAGE_PROCESSING_CONCURRENCY: int = 2

    # 调试/测试 API(/api/v1/_debug/*, /api/v1/test/*)是否开启;默认关闭,需要时显式打开
    ENABLE_DEBUG_API: bool = False

    # Trace ID:仅当前置可信反向代理(由网关设置并覆盖 X-Trace-Id)时置 true;
    # 公网直连 / 无网关时保持 false,一律服务端生成。
    TRUST_INBOUND_TRACE_ID: bool = False

    # 真实客户端 IP:仅当前置可信反向代理覆盖 X-Real-IP / X-Forwarded-For 时开启。
    TRUST_PROXY: bool = False

    # WhatsApp 客服号码(允许带 +、空格、横线,解析时规范化)
    WHATSAPP_DEFAULT_NUMBER: str = "+255 758 311 131"

    # 客服邮箱
    CONTACT_EMAIL: str = "info@buildreach.co.tz"

    # 地推演示白名单(逗号分隔的 Buyer 邮箱，可看到 mock 订单追踪数据)
    DEMO_EMAILS: str = ""

    # Refresh token cookie 配置(本机 http 开发用 SECURE=False;生产 https 必须 True)
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    REFRESH_COOKIE_MAX_AGE: int = 7 * 24 * 3600  # 7 天,与 refresh JWT TTL 一致
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_SAMESITE: str = "lax"  # lax: 同站刷新/导航会带 cookie; strict 会阻止地址栏刷新带 cookie

    # CORS 允许携带凭证(refresh cookie 必需)
    CORS_ALLOW_CREDENTIALS: bool = True

    # SMTP 邮件（验证码）— 生产未配置时 fail-fast;本地可显式开启日志打印验证码。
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@matgo.co.tz"
    SMTP_USE_TLS: bool = True
    EMAIL_DEV_LOG_CODES: bool = False

    # 邮箱验证码
    VERIFICATION_CODE_LENGTH: int = 6
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 15
    VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 10
    VERIFICATION_CODE_COOLDOWN_SECONDS: int = 60
    VERIFICATION_CODE_MAX_ATTEMPTS: int = 5
    VERIFICATION_CODE_IP_HOURLY_LIMIT: int = 20

    @computed_field  # type: ignore[misc]
    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [s.strip() for s in self.CORS_ORIGINS_RAW.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
