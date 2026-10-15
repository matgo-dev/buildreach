# 矿业勘探·开采专区 导入资料

- `spu_merge.csv` 品名合并表:原品名 → SPU 品名 + 规格;规格留空 = 纯别名。导入脚本与找图清单共用。
- `rules.csv` 映射规则:(file_key, sheet, section, keyword) → (专区大类 C01..C11, 平台品类 code)。
  优先级:文件专属关键词 > 通配(*)关键词 > 无关键词(环节/sheet 兜底);同级按行序第一条命中。
  平台品类本期允许一级 code 粗占位(01 劳保 / 04 手动工具 / 07 机电 / 08 紧固件 / 10 电器 / 11 灯具 / 12 电缆 / 14 工控 / 15 电工辅料 / 18 涂料化工 / 21 土建 / 28 塑胶管道)或新建的 33.x / 34.x / 35.x 叶子。
- `矿业专区_找图清单.xlsx` 发九云的找图输入(商品编号 = spu_code,由导入脚本同一套解析生成),不入库。
- `dry_run_audit.csv` dry-run 产物,gitignore;「命中规则」列说明每件商品为什么落在那个大类,发廖总团队核对就看这张。「属性差异」列记同一 SPU 在不同文件里环节/是否通用不一致的行(取第一个非空值入库,只提示不阻断)。
- `dry_run_dropped.csv` dry-run 产物,gitignore;被噪声规则(待核/合计/…方案/…服务/…报表)或品名超 60 字过滤掉的源行,每次都要扫一眼确认没把真商品当噪声丢了。

**品名冻结**:spu_code 由 SPU 品名算出。`spu_merge.csv` 里的 SPU 品名一旦 `--commit` 过、或找图清单已发九云,就不要再改——改名等于换编号,旧商品会变成孤儿(脚本会拒绝落库,只有 `--prune-orphans` 才软删旧商品并清其挂载),九云按旧编号交回的图也对不上。要改名请在首次落库前、发清单前做。

**改规则重跑**:`rules.csv` 改大类后直接重跑 `--commit`,脚本会清掉本批次写入、但已不在新结果里的 zone_products 行(手工挂的不动),计数在 `zone_products_removed`。

**改规格不能重跑**:已 `--commit` 过的商品,`spu_merge.csv` 里加/删规格不会自动增删 SKU(会动已有引用)。脚本对比库内活 SKU 与期望集合,不一致记在 `sku_mismatches` 并拒绝落库;要改规格先人工处理该商品的 SKU。

**--prune-orphans** 软删孤儿商品时连其 SKU 一起软删(sku_code 由 spu_code+规格确定,活 SKU 留着会让改回品名后的重导撞唯一索引)。

源表(不在仓库):`矿业专区资料/` 6 个 xlsx(01 浮选厂 / 02 井下 / 03 化验室 / 04 CIP·CIL / 05 露天 / 600 型钻机)。

执行:

    cd backend
    python scripts/import_zone_mining.py --src <目录> --dry-run   # 未命中/冲突/SKU 不一致须为 0,审核 CSV 抽查,丢弃 CSV 过目
    python scripts/import_zone_mining.py --src <目录> --commit    # 幂等,可重跑;有孤儿商品会拒绝,确认后加 --prune-orphans
    python scripts/backfill_translations.py --entity all          # 补 en/sw

生产:镜像不含 data/,先把源表 + 本目录拷到主机,再 docker cp 进容器(脚本按仓库相对路径读 data/zone_import/mining/*.csv,容器内需放到 /app/data/zone_import/mining/);--commit 时只要 DATABASE_URL 的主机不是本机(容器里是 compose 服务名 db,staging 和生产都算)就必须 ALLOW_ZONE_IMPORT_PROD=1,守卫在 scripts/_zone_import_common.py,央企脚本同一份。

2026-10-14 本地落库计数:763 SPU(25 个多规格,共 800 SKU)、1609 条 zone_products(763 大类 + 846 场景)、平台品类 33/34/35 子树 13 个节点(全部停用)。

**采购说明不当描述**:源表「参考型号/规格」列是写给采购员的(按…核对/预算示例/待核),导入存到 `products.source_meta.purchase_note`,只在运营商品详情显示为「采购备注」;买家端描述留空。占位值(未列/原PDF未列规格/待确认)在解析层当空,新发现的加进脚本里的占位集合。
