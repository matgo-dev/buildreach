"""集中导入所有模型,供 Alembic autogenerate 识别。"""
from app.db.models.audit_log import AuditLog
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.category import Category, CategoryLevel
from app.db.models.credit_ai_conversation import CreditAiConversation
from app.db.models.credit_ai_message import CreditAiMessage, MessageRole
from app.db.models.credit_company import CreditCompany
from app.db.models.credit_company_basic_data import (
    CreditCompanyBasicData,
    DataSourceTag,
)
from app.db.models.credit_company_certification import (
    CertStatus,
    CertType,
    CreditCompanyCertification,
)
from app.db.models.credit_company_finance_data import (
    CashFlowStatus,
    CreditCompanyFinanceData,
    RevenueTrend,
)
from app.db.models.credit_company_legal_data import (
    CreditCompanyLegalData,
    NegativeNewsLevel,
)
from app.db.models.credit_data_harvest_run import (
    CreditDataHarvestRun,
    HarvestRunStatus,
    HarvestTriggeredBy,
)
from app.db.models.credit_search_history import CreditSearchHistory
from app.db.models.attr_template import AttrTemplate
from app.db.models.permission import Permission
from app.db.models.product import Product, ProductStatus
from app.db.models.product_attr import ProductAttr
from app.db.models.product_image import ProductImage
from app.db.models.product_supplier import ProductSupplier
from app.db.models.role import Role
from app.db.models.role_permission import RolePermission
from app.db.models.score_audit_log import ScoreAuditLog
from app.db.models.score_detail import ScoreDetail
from app.db.models.score_dimension import DimensionCode, ScoreDimension
from app.db.models.score_dimension_override import ScoreDimensionOverride
from app.db.models.score_rule import ScoreRule
from app.db.models.score_snapshot import Grade, ScoreSnapshot, TriggerType
from app.db.models.score_subitem import ScoreSubitem
from app.db.models.supplier_member import SupplierMember
from app.db.models.supplier_organization import SupplierOrganization
from app.db.models.translation_glossary import TranslationGlossary
from app.db.models.user import User
from app.db.models.user_role import UserRole

__all__ = [
    # auth / rbac / org
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "BuyerOrganization",
    "SupplierOrganization",
    "BuyerMember",
    "SupplierMember",
    "AuditLog",
    # category
    "Category",
    "CategoryLevel",
    # product catalog
    "Product",
    "ProductStatus",
    "ProductImage",
    "ProductAttr",
    "ProductSupplier",
    "AttrTemplate",
    # credit assessment - 评分模型骨架
    "ScoreDimension",
    "DimensionCode",
    "ScoreSubitem",
    "ScoreRule",
    "ScoreDimensionOverride",
    # credit assessment - 企业与数据快照
    "CreditCompany",
    "CreditCompanyBasicData",
    "DataSourceTag",
    "CreditCompanyFinanceData",
    "RevenueTrend",
    "CashFlowStatus",
    "CreditCompanyLegalData",
    "NegativeNewsLevel",
    "CreditCompanyCertification",
    "CertType",
    "CertStatus",
    "CreditDataHarvestRun",
    "HarvestRunStatus",
    "HarvestTriggeredBy",
    # credit assessment - 评分结果
    "ScoreSnapshot",
    "Grade",
    "TriggerType",
    "ScoreDetail",
    "ScoreAuditLog",
    # credit assessment - 用户交互
    "CreditSearchHistory",
    "CreditAiConversation",
    "CreditAiMessage",
    "MessageRole",
    # i18n
    "TranslationGlossary",
]
