# 矿业勘探·开采专区 导入资料

- `spu_merge.csv` 品名合并表:原品名 → SPU 品名 + 规格;规格留空 = 纯别名。导入脚本与找图清单共用。
- `rules.csv` 映射规则:(file_key, sheet, section, keyword) → (专区大类 C01..C11, 平台品类 code)。
  优先级:文件专属关键词 > 通配(*)关键词 > 无关键词(环节/sheet 兜底);同级按行序第一条命中。
  平台品类本期允许一级 code 粗占位(01 劳保 / 04 手动工具 / 07 机电 / 08 紧固件 / 10 电器 / 11 灯具 / 12 电缆 / 14 工控 / 15 电工辅料 / 18 涂料化工 / 21 土建 / 28 塑胶管道)或新建的 33.x / 34.x / 35.x 叶子。
- `矿业专区_找图清单.xlsx` 发九云的找图输入(商品编号 = spu_code,由导入脚本同一套解析生成),不入库。
- `dry_run_audit.csv` dry-run 产物,gitignore。

源表(不在仓库):`矿业专区资料/` 6 个 xlsx(01 浮选厂 / 02 井下 / 03 化验室 / 04 CIP·CIL / 05 露天 / 600 型钻机)。

执行:

    cd backend
    python scripts/import_zone_mining.py --src <目录> --dry-run   # 未命中/冲突须为 0,审核 CSV 抽查
    python scripts/import_zone_mining.py --src <目录> --commit    # 幂等,可重跑
    python scripts/backfill_translations.py --entity all          # 补 en/sw

生产:镜像不含 data/,先把源表 + 本目录拷到主机,再 docker cp 进容器(脚本按仓库相对路径读 data/zone_import/mining/*.csv,容器内需放到 /app/data/zone_import/mining/);--commit 须 ALLOW_ZONE_IMPORT_PROD=1。

2026-10-14 本地落库计数:764 SPU(25 个多规格,共 800 SKU)、1611 条 zone_products(764 大类 + 847 场景)、平台品类 33/34/35 子树 13 个节点(全部停用)。
