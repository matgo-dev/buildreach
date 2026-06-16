"""报价行类型枚举。"""


class QuoteLineType:
    PRODUCT = "PRODUCT"  # 商品行（回应/替代都是给商品报价）
    FEE = "FEE"          # 费用行（包装/运费/检测/报关等整单费用）
    ALL = (PRODUCT, FEE)
