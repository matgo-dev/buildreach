# XFS 商品图片 S3 Key 与交付约定

本文档用于约定 XFS 采集批次中的商品图片上传到对象存储后，平台导入业务数据所需的文件和字段。

## 交付结构

沿用现有采集批次结构，去掉图片文件本体 `images/` 即可。

平台需要的批次结构示例：

```text
output_xfs_xxx/
  run.json
  categories_raw.json
  _report.json
  _problems.json
  categories/
    {一级类目}/
      {二级类目}/
        .../
          offers/
            {spuCode}/
              offer.json
  s3_manifest.jsonl
```

图片上传结果统一记录在 `s3_manifest.jsonl`。

## Object Key 规则

`platformSpuCode` 使用平台商品编码，规则如下：

```text
platformSpuCode = "MG-P" + hash12
hash12 = SHA256("P:XFS:" + xfs_spuCode).十六进制前 12 位大写
```

示例：

```text
xfs_spuCode = 3014838
message = "P:XFS:3014838"
SHA256(message).前 12 位大写 = 91AA258E57A7
platformSpuCode = MG-P91AA258E57A7
```

对象存储 key 规则如下：

```text
主图第一张：
products/xfs/{platformSpuCode}/main/{原文件名}

其他主图/轮播图：
products/xfs/{platformSpuCode}/gallery/{原文件名}

详情图：
products/xfs/{platformSpuCode}/detail/{原文件名}

缩略图：
与原图同目录，文件名为 {原文件名不含扩展名}_thumb.webp
格式为 WebP，最长边 300px，等比例缩放
```

示例：

```text
images/main_01.jpg
-> products/xfs/MG-P91AA258E57A7/main/main_01.jpg

images/main_02.jpg
-> products/xfs/MG-P91AA258E57A7/gallery/main_02.jpg

images/detail_01.jpg
-> products/xfs/MG-P91AA258E57A7/detail/detail_01.jpg

images/main_01.jpg 的缩略图
-> products/xfs/MG-P91AA258E57A7/main/main_01_thumb.webp
```

## s3_manifest.jsonl

`s3_manifest.jsonl` 是图片上传清单。平台导入商品数据时会通过它把 `offer.json` 中的图片记录和对象存储中的 `objectKey` 对应起来。

格式：

```text
一行一张图片
每行一个 JSON 对象
文件名：s3_manifest.jsonl
```

示例：

```json
{"spuCode":"3014838","platformSpuCode":"MG-P91AA258E57A7","imageType":"MAIN","sortOrder":0,"offerPath":"categories/气动液压/液压辅助元件/液压管路/高压胶管/offers/3014838/offer.json","localPath":"categories/气动液压/液压辅助元件/液压管路/高压胶管/offers/3014838/images/main_01.jpg","sourceUrl":"https://fsyuncai.oss-cn-beijing.aliyuncs.com/xxx.jpg","objectKey":"products/xfs/MG-P91AA258E57A7/main/main_01.jpg","thumbKey":"products/xfs/MG-P91AA258E57A7/main/main_01_thumb.webp","width":800,"height":800,"fileSize":111484,"contentType":"image/jpeg","status":"uploaded"}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `spuCode` | 是 | XFS 原始 `spuCode` |
| `platformSpuCode` | 是 | 平台商品编码 |
| `imageType` | 是 | `MAIN` / `GALLERY` / `DETAIL` |
| `sortOrder` | 是 | 图片排序 |
| `offerPath` | 是 | 对应 `offer.json` 的批次内相对路径 |
| `localPath` | 是 | 原始本地图片的批次内相对路径 |
| `sourceUrl` | 否 | XFS 原始图片 URL，有则保留 |
| `objectKey` | 是 | 上传到对象存储后的正式图片 key |
| `thumbKey` | 否 | 缩略图 key，没有则为空或省略 |
| `width` | 否 | 图片宽度 |
| `height` | 否 | 图片高度 |
| `fileSize` | 否 | 图片文件大小，单位 byte |
| `contentType` | 否 | 如 `image/jpeg`、`image/png`、`image/webp` |
| `thumbSize` | 否 | 缩略图文件大小，单位 byte |
| `status` | 是 | `uploaded` / `failed` / `skipped` / `exists` / `dry_run` |
| `error` | 否 | 上传失败时填写错误信息 |

## 平台导入时如何使用

平台导入逻辑：

```text
1. 读取 categories_raw.json，导入或补齐品类
2. 扫描原批次结构中的所有 offer.json
3. 读取 s3_manifest.jsonl
4. 通过 spuCode + localPath 或 offerPath + localPath 匹配图片
5. 导入 products / product_skus / product_attrs
6. 写入 product_images.image_key = objectKey
```

最终平台数据库只保存对象存储 key，例如：

```text
products/xfs/MG-P91AA258E57A7/main/main_01.jpg
```
