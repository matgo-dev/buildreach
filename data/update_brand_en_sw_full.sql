-- 品牌 brand_en / brand_sw 批量更新
-- 2026-06-27 基于线上 1426 个品牌整理
-- brand_sw 直接等于 brand_en（品牌名不翻译斯瓦希里语）
-- 强制覆盖所有记录（异步翻译管道的自动翻译都是错的）

BEGIN;

-- ══════════════════════════════════════════════════════════
-- 零、先把所有品牌 brand_en/sw 重置为 brand_zh（清除错误的自动翻译）
-- 后续精确 UPDATE 会覆盖为正确英文名
-- ══════════════════════════════════════════════════════════
UPDATE products
SET brand_en = brand_zh,
    brand_sw = brand_zh
WHERE brand_zh IS NOT NULL AND brand_zh != '';

-- ══════════════════════════════════════════════════════════
-- 一、国际知名品牌（官方英文名）
-- ══════════════════════════════════════════════════════════
UPDATE products SET brand_en='A.O. Smith', brand_sw='A.O. Smith' WHERE brand_zh='A.O. 史密斯';
UPDATE products SET brand_en='Panasonic', brand_sw='Panasonic' WHERE brand_zh='松下';
UPDATE products SET brand_en='Siemens', brand_sw='Siemens' WHERE brand_zh='西门子';
UPDATE products SET brand_en='Philips', brand_sw='Philips' WHERE brand_zh='飞利浦';
UPDATE products SET brand_en='Schneider Electric', brand_sw='Schneider Electric' WHERE brand_zh='施耐德电气';
UPDATE products SET brand_en='Honeywell', brand_sw='Honeywell' WHERE brand_zh='霍尼韦尔';
UPDATE products SET brand_en='OMRON', brand_sw='OMRON' WHERE brand_zh='欧姆龙';
UPDATE products SET brand_en='OMRON', brand_sw='OMRON' WHERE brand_zh='欧姆龙(OMRON)';
UPDATE products SET brand_en='Mitsubishi', brand_sw='Mitsubishi' WHERE brand_zh='三菱';
UPDATE products SET brand_en='Bosch', brand_sw='Bosch' WHERE brand_zh='博世';
UPDATE products SET brand_en='Stanley', brand_sw='Stanley' WHERE brand_zh='史丹利';
UPDATE products SET brand_en='Hilti', brand_sw='Hilti' WHERE brand_zh='喜利得';
UPDATE products SET brand_en='Festo', brand_sw='Festo' WHERE brand_zh='费斯托';
UPDATE products SET brand_en='BASF', brand_sw='BASF' WHERE brand_zh='巴斯夫';
UPDATE products SET brand_en='Deltaplus', brand_sw='Deltaplus' WHERE brand_zh='代尔塔';
UPDATE products SET brand_en='Dow Corning', brand_sw='Dow Corning' WHERE brand_zh='道康宁';
UPDATE products SET brand_en='Knipex', brand_sw='Knipex' WHERE brand_zh='凯尼派克';
UPDATE products SET brand_en='Eaton', brand_sw='Eaton' WHERE brand_zh='伊顿';
UPDATE products SET brand_en='Loctite', brand_sw='Loctite' WHERE brand_zh='乐泰';
UPDATE products SET brand_en='Beta', brand_sw='Beta' WHERE brand_zh='百塔';
UPDATE products SET brand_en='Beta', brand_sw='Beta' WHERE brand_zh='百塔Beta';
UPDATE products SET brand_en='Motorola', brand_sw='Motorola' WHERE brand_zh='摩托罗拉';
UPDATE products SET brand_en='Wurth', brand_sw='Wurth' WHERE brand_zh='伍尔特';
UPDATE products SET brand_en='Kohler', brand_sw='Kohler' WHERE brand_zh='科勒';
UPDATE products SET brand_en='ISCAR', brand_sw='ISCAR' WHERE brand_zh='伊斯卡';
UPDATE products SET brand_en='Henkel Pattex', brand_sw='Henkel Pattex' WHERE brand_zh='汉高百得';
UPDATE products SET brand_en='Legrand', brand_sw='Legrand' WHERE brand_zh='罗格朗';
UPDATE products SET brand_en='Phoenix Contact', brand_sw='Phoenix Contact' WHERE brand_zh='菲尼克斯';
UPDATE products SET brand_en='Moxa', brand_sw='Moxa' WHERE brand_zh='摩莎';
UPDATE products SET brand_en='Endress+Hauser', brand_sw='Endress+Hauser' WHERE brand_zh='恩德斯豪斯';
UPDATE products SET brand_en='OSRAM', brand_sw='OSRAM' WHERE brand_zh='欧司朗';
UPDATE products SET brand_en='Sandvik', brand_sw='Sandvik' WHERE brand_zh='山特维克';
UPDATE products SET brand_en='Santak', brand_sw='Santak' WHERE brand_zh='山特';
UPDATE products SET brand_en='Grundfos', brand_sw='Grundfos' WHERE brand_zh='格兰富';
UPDATE products SET brand_en='Wilo', brand_sw='Wilo' WHERE brand_zh='威乐';
UPDATE products SET brand_en='MSA Safety', brand_sw='MSA Safety' WHERE brand_zh='梅思安';
UPDATE products SET brand_en='DORMA', brand_sw='DORMA' WHERE brand_zh='多玛';
UPDATE products SET brand_en='Armstrong', brand_sw='Armstrong' WHERE brand_zh='阿姆斯壮';
UPDATE products SET brand_en='Tohnichi', brand_sw='Tohnichi' WHERE brand_zh='东日';
UPDATE products SET brand_en='Mahr', brand_sw='Mahr' WHERE brand_zh='马尔';
UPDATE products SET brand_en='REMA TIP TOP', brand_sw='REMA TIP TOP' WHERE brand_zh='蒂普拓普';
UPDATE products SET brand_en='Baumer', brand_sw='Baumer' WHERE brand_zh='堡盟';
UPDATE products SET brand_en='SICK', brand_sw='SICK' WHERE brand_zh='西克';
UPDATE products SET brand_en='Justrite', brand_sw='Justrite' WHERE brand_zh='杰斯瑞特';
UPDATE products SET brand_en='COMMSCOPE', brand_sw='COMMSCOPE' WHERE brand_zh='康普';
UPDATE products SET brand_en='Yale', brand_sw='Yale' WHERE brand_zh='耶鲁';
UPDATE products SET brand_en='Ansell', brand_sw='Ansell' WHERE brand_zh='安思尔';

-- ══════════════════════════════════════════════════════════
-- 二、知名中国品牌（有官方英文名）
-- ══════════════════════════════════════════════════════════
UPDATE products SET brand_en='CHINT', brand_sw='CHINT' WHERE brand_zh='正泰';
UPDATE products SET brand_en='Delixi', brand_sw='Delixi' WHERE brand_zh='德力西';
UPDATE products SET brand_en='Deli', brand_sw='Deli' WHERE brand_zh='得力';
UPDATE products SET brand_en='Deli Tools', brand_sw='Deli Tools' WHERE brand_zh='得力工具';
UPDATE products SET brand_en='SATA', brand_sw='SATA' WHERE brand_zh='世达';
UPDATE products SET brand_en='LESSO', brand_sw='LESSO' WHERE brand_zh='联塑';
UPDATE products SET brand_en='Rifeng', brand_sw='Rifeng' WHERE brand_zh='日丰';
UPDATE products SET brand_en='Far East Cable', brand_sw='Far East Cable' WHERE brand_zh='远东电缆';
UPDATE products SET brand_en='Far East Cable', brand_sw='Far East Cable' WHERE brand_zh='远东';
UPDATE products SET brand_en='AirTAC', brand_sw='AirTAC' WHERE brand_zh='亚德客';
UPDATE products SET brand_en='AMICO', brand_sw='AMICO' WHERE brand_zh='埃美柯';
UPDATE products SET brand_en='Great Wall Seiko', brand_sw='Great Wall Seiko' WHERE brand_zh='长城精工';
UPDATE products SET brand_en='Qifan Cable', brand_sw='Qifan Cable' WHERE brand_zh='起帆';
UPDATE products SET brand_en='Shangshang Cable', brand_sw='Shangshang Cable' WHERE brand_zh='上上';
UPDATE products SET brand_en='Aucma', brand_sw='Aucma' WHERE brand_zh='澳柯玛';
UPDATE products SET brand_en='SAFEWARE', brand_sw='SAFEWARE' WHERE brand_zh='安赛瑞';
UPDATE products SET brand_en='HESIDIK', brand_sw='HESIDIK' WHERE brand_zh='海斯迪克';
UPDATE products SET brand_en='Jianzhi', brand_sw='Jianzhi' WHERE brand_zh='建支';
UPDATE products SET brand_en='Pengchi', brand_sw='Pengchi' WHERE brand_zh='鹏驰';
UPDATE products SET brand_en='Haier', brand_sw='Haier' WHERE brand_zh='海尔';
UPDATE products SET brand_en='Midea', brand_sw='Midea' WHERE brand_zh='美的';
UPDATE products SET brand_en='GREE', brand_sw='GREE' WHERE brand_zh='格力 GREE';
UPDATE products SET brand_en='Xiaomi', brand_sw='Xiaomi' WHERE brand_zh='小米';
UPDATE products SET brand_en='Hikvision', brand_sw='Hikvision' WHERE brand_zh='海康威视';
UPDATE products SET brand_en='JOMOO', brand_sw='JOMOO' WHERE brand_zh='九牧';
UPDATE products SET brand_en='SUPOR', brand_sw='SUPOR' WHERE brand_zh='苏泊尔';
UPDATE products SET brand_en='BULL', brand_sw='BULL' WHERE brand_zh='公牛';
UPDATE products SET brand_en='OPPLE', brand_sw='OPPLE' WHERE brand_zh='欧普照明';
UPDATE products SET brand_en='NVC Lighting', brand_sw='NVC Lighting' WHERE brand_zh='雷士照明';
UPDATE products SET brand_en='ARROW', brand_sw='ARROW' WHERE brand_zh='箭牌';
UPDATE products SET brand_en='FSL', brand_sw='FSL' WHERE brand_zh='佛山照明';
UPDATE products SET brand_en='SANY', brand_sw='SANY' WHERE brand_zh='三一重工';
UPDATE products SET brand_en='Oriental Yuhong', brand_sw='Oriental Yuhong' WHERE brand_zh='东方雨虹';
UPDATE products SET brand_en='Tubao', brand_sw='Tubao' WHERE brand_zh='兔宝宝';
UPDATE products SET brand_en='Konka', brand_sw='Konka' WHERE brand_zh='康佳';
UPDATE products SET brand_en='AUX', brand_sw='AUX' WHERE brand_zh='奥克斯';
UPDATE products SET brand_en='Micoe', brand_sw='Micoe' WHERE brand_zh='四季沐歌';
UPDATE products SET brand_en='Nippon Paint', brand_sw='Nippon Paint' WHERE brand_zh='立邦';
UPDATE products SET brand_en='Joyoung', brand_sw='Joyoung' WHERE brand_zh='九阳';
UPDATE products SET brand_en='ECOVACS', brand_sw='ECOVACS' WHERE brand_zh='科沃斯机器人  ECOVACS';
UPDATE products SET brand_en='FOTILE', brand_sw='FOTILE' WHERE brand_zh='方太';
UPDATE products SET brand_en='Dongcheng', brand_sw='Dongcheng' WHERE brand_zh='东成';
UPDATE products SET brand_en='CHNT Tianzheng', brand_sw='CHNT Tianzheng' WHERE brand_zh='天正电气';
UPDATE products SET brand_en='Hisense', brand_sw='Hisense' WHERE brand_zh='海信';
UPDATE products SET brand_en='DJI', brand_sw='DJI' WHERE brand_zh='大疆';
UPDATE products SET brand_en='Dahua', brand_sw='Dahua' WHERE brand_zh='大华';
UPDATE products SET brand_en='Little Swan', brand_sw='Little Swan' WHERE brand_zh='小天鹅';
UPDATE products SET brand_en='Bear', brand_sw='Bear' WHERE brand_zh='小熊';
UPDATE products SET brand_en='VASEN', brand_sw='VASEN' WHERE brand_zh='VASEN 伟星';
UPDATE products SET brand_en='TP-LINK', brand_sw='TP-LINK' WHERE brand_zh='TP-LINK';
UPDATE products SET brand_en='Ruijie', brand_sw='Ruijie' WHERE brand_zh='锐捷';
UPDATE products SET brand_en='ERA', brand_sw='ERA' WHERE brand_zh='公元 ERA';
UPDATE products SET brand_en='Hengtong', brand_sw='Hengtong' WHERE brand_zh='亨通';
UPDATE products SET brand_en='Worx', brand_sw='Worx' WHERE brand_zh='威克士（WORX）';
UPDATE products SET brand_en='Panpan', brand_sw='Panpan' WHERE brand_zh='盼盼';
UPDATE products SET brand_en='TopStrong', brand_sw='TopStrong' WHERE brand_zh='顶固';
UPDATE products SET brand_en='Warrior', brand_sw='Warrior' WHERE brand_zh='回力';
UPDATE products SET brand_en='Morphy Richards', brand_sw='Morphy Richards' WHERE brand_zh='摩飞';
UPDATE products SET brand_en='Yankon', brand_sw='Yankon' WHERE brand_zh='亚明照明';
UPDATE products SET brand_en='Casarte', brand_sw='Casarte' WHERE brand_zh='卡萨帝';
UPDATE products SET brand_en='Kaifeng', brand_sw='Kaifeng' WHERE brand_zh='凯泉';
UPDATE products SET brand_en='Sunrain', brand_sw='Sunrain' WHERE brand_zh='太阳花';
UPDATE products SET brand_en='Dulux', brand_sw='Dulux' WHERE brand_zh='多乐士';
UPDATE products SET brand_en='OUJING', brand_sw='OUJING' WHERE brand_zh='欧井';
UPDATE products SET brand_en='Lexy', brand_sw='Lexy' WHERE brand_zh='莱克 LEXY';
UPDATE products SET brand_en='MIJIA', brand_sw='MIJIA' WHERE brand_zh='米家';
UPDATE products SET brand_en='Theodore', brand_sw='Theodore' WHERE brand_zh='西奥多';
UPDATE products SET brand_en='Lenovo', brand_sw='Lenovo' WHERE brand_zh='联想';
UPDATE products SET brand_en='HEGII', brand_sw='HEGII' WHERE brand_zh='恒洁';
UPDATE products SET brand_en='HUIDA', brand_sw='HUIDA' WHERE brand_zh='惠达';
UPDATE products SET brand_en='CANBO', brand_sw='CANBO' WHERE brand_zh='康宝 CANBO';
UPDATE products SET brand_en='Seagull', brand_sw='Seagull' WHERE brand_zh='海鸥';
UPDATE products SET brand_en='HGST', brand_sw='HGST' WHERE brand_zh='鸿雁';
UPDATE products SET brand_en='Chigo', brand_sw='Chigo' WHERE brand_zh='志高';
UPDATE products SET brand_en='Davey', brand_sw='Davey' WHERE brand_zh='德玛仕';
UPDATE products SET brand_en='Livinglab', brand_sw='Livinglab' WHERE brand_zh='乐光';
UPDATE products SET brand_en='Lock&Lock', brand_sw='Lock&Lock' WHERE brand_zh='乐扣乐扣';
UPDATE products SET brand_en='Delta', brand_sw='Delta' WHERE brand_zh='台达';
UPDATE products SET brand_en='BOE', brand_sw='BOE' WHERE brand_zh='京东方';
UPDATE products SET brand_en='Shenli', brand_sw='Shenli' WHERE brand_zh='申鹭达';
UPDATE products SET brand_en='Baosteel', brand_sw='Baosteel' WHERE brand_zh='宝胜';
UPDATE products SET brand_en='Moganshan', brand_sw='Moganshan' WHERE brand_zh='莫干山';
UPDATE products SET brand_en='Oatey', brand_sw='Oatey' WHERE brand_zh='欧泰';
UPDATE products SET brand_en='Nanfang Pump', brand_sw='Nanfang Pump' WHERE brand_zh='南方测绘';
UPDATE products SET brand_en='WAROM', brand_sw='WAROM' WHERE brand_zh='华荣';
UPDATE products SET brand_en='Lechange', brand_sw='Lechange' WHERE brand_zh='乐创';
UPDATE products SET brand_en='Qiangli', brand_sw='Qiangli' WHERE brand_zh='强力';

-- ══════════════════════════════════════════════════════════
-- 三、中国品牌（拼音 romanization）
-- ══════════════════════════════════════════════════════════
UPDATE products SET brand_en='Jianli', brand_sw='Jianli' WHERE brand_zh='剑力';
UPDATE products SET brand_en='Jianli', brand_sw='Jianli' WHERE brand_zh='剑力 JL';
UPDATE products SET brand_en='Jianli', brand_sw='Jianli' WHERE brand_zh='.剑力';
UPDATE products SET brand_en='Dunshi', brand_sw='Dunshi' WHERE brand_zh='盾石';
UPDATE products SET brand_en='Jinggu', brand_sw='Jinggu' WHERE brand_zh='京固';
UPDATE products SET brand_en='Tianfeng', brand_sw='Tianfeng' WHERE brand_zh='天峰';
UPDATE products SET brand_en='Helisi', brand_sw='Helisi' WHERE brand_zh='赫力斯';
UPDATE products SET brand_en='Lianzhu', brand_sw='Lianzhu' WHERE brand_zh='联铸';
UPDATE products SET brand_en='Zhongze', brand_sw='Zhongze' WHERE brand_zh='中泽';
UPDATE products SET brand_en='Fanshi', brand_sw='Fanshi' WHERE brand_zh='泛氏';
UPDATE products SET brand_en='Mingtong', brand_sw='Mingtong' WHERE brand_zh='铭通';
UPDATE products SET brand_en='Fengsu', brand_sw='Fengsu' WHERE brand_zh='峰塑';
UPDATE products SET brand_en='Mingli', brand_sw='Mingli' WHERE brand_zh='名利';
UPDATE products SET brand_en='Xianyu', brand_sw='Xianyu' WHERE brand_zh='宪宇';
UPDATE products SET brand_en='Haliang', brand_sw='Haliang' WHERE brand_zh='哈量';
UPDATE products SET brand_en='Sanhui', brand_sw='Sanhui' WHERE brand_zh='三辉';
UPDATE products SET brand_en='Huyang', brand_sw='Huyang' WHERE brand_zh='沪洋';
UPDATE products SET brand_en='Jielin', brand_sw='Jielin' WHERE brand_zh='洁林';
UPDATE products SET brand_en='Yonggu', brand_sw='Yonggu' WHERE brand_zh='涌固';
UPDATE products SET brand_en='Domestic Premium', brand_sw='Domestic Premium' WHERE brand_zh='国产优品';
UPDATE products SET brand_en='Green Island', brand_sw='Green Island' WHERE brand_zh='绿岛';
UPDATE products SET brand_en='Bito', brand_sw='Bito' WHERE brand_zh='必拓';
UPDATE products SET brand_en='Wucai', brand_sw='Wucai' WHERE brand_zh='五彩';
UPDATE products SET brand_en='Tianbao', brand_sw='Tianbao' WHERE brand_zh='天宝';
UPDATE products SET brand_en='Haijing', brand_sw='Haijing' WHERE brand_zh='海井';
UPDATE products SET brand_en='Bingyu', brand_sw='Bingyu' WHERE brand_zh='冰禹';
UPDATE products SET brand_en='Woodpecker', brand_sw='Woodpecker' WHERE brand_zh='京南啄木鸟';
UPDATE products SET brand_en='Jingtong', brand_sw='Jingtong' WHERE brand_zh='京通';
UPDATE products SET brand_en='Qingniao', brand_sw='Qingniao' WHERE brand_zh='青鸟';
UPDATE products SET brand_en='REGAL', brand_sw='REGAL' WHERE brand_zh='锐阁';
UPDATE products SET brand_en='Jianqiang', brand_sw='Jianqiang' WHERE brand_zh='建强';
UPDATE products SET brand_en='Jiangang', brand_sw='Jiangang' WHERE brand_zh='建钢';
UPDATE products SET brand_en='Yili', brand_sw='Yili' WHERE brand_zh='一力';
UPDATE products SET brand_en='Dingnan', brand_sw='Dingnan' WHERE brand_zh='丁南';
UPDATE products SET brand_en='Qiwei', brand_sw='Qiwei' WHERE brand_zh='七维';
UPDATE products SET brand_en='Wanquan', brand_sw='Wanquan' WHERE brand_zh='万全';
UPDATE products SET brand_en='Wanzun', brand_sw='Wanzun' WHERE brand_zh='万尊';
UPDATE products SET brand_en='Wanfang', brand_sw='Wanfang' WHERE brand_zh='万方管业';
UPDATE products SET brand_en='Wanmulin', brand_sw='Wanmulin' WHERE brand_zh='万木林';
UPDATE products SET brand_en='Wanlin', brand_sw='Wanlin' WHERE brand_zh='万林';
UPDATE products SET brand_en='Wanluo', brand_sw='Wanluo' WHERE brand_zh='万螺';
UPDATE products SET brand_en='Wangu', brand_sw='Wangu' WHERE brand_zh='万谷';
UPDATE products SET brand_en='Wanda', brand_sw='Wanda' WHERE brand_zh='万达';
UPDATE products SET brand_en='Sanfeng', brand_sw='Sanfeng' WHERE brand_zh='三丰';
UPDATE products SET brand_en='Sanyou', brand_sw='Sanyou' WHERE brand_zh='三佑';
UPDATE products SET brand_en='Sanxie', brand_sw='Sanxie' WHERE brand_zh='三协';
UPDATE products SET brand_en='Sanhe', brand_sw='Sanhe' WHERE brand_zh='三和';
UPDATE products SET brand_en='Sanxia', brand_sw='Sanxia' WHERE brand_zh='三峡';
UPDATE products SET brand_en='Sanqing', brand_sw='Sanqing' WHERE brand_zh='三庆';
UPDATE products SET brand_en='Sanjiang', brand_sw='Sanjiang' WHERE brand_zh='三江电子';
UPDATE products SET brand_en='Sanhuan', brand_sw='Sanhuan' WHERE brand_zh='三环';
UPDATE products SET brand_en='Sanshe', brand_sw='Sanshe' WHERE brand_zh='三社';
UPDATE products SET brand_en='Sanneng', brand_sw='Sanneng' WHERE brand_zh='三能';
UPDATE products SET brand_en='Sanliang', brand_sw='Sanliang' WHERE brand_zh='三量';
UPDATE products SET brand_en='Sanlu', brand_sw='Sanlu' WHERE brand_zh='三鹿';
UPDATE products SET brand_en='Shangyu', brand_sw='Shangyu' WHERE brand_zh='上宇';
UPDATE products SET brand_en='Shanggong', brand_sw='Shanggong' WHERE brand_zh='上工';
UPDATE products SET brand_en='Shangke', brand_sw='Shangke' WHERE brand_zh='上柯';
UPDATE products SET brand_en='Shangyu', brand_sw='Shangyu' WHERE brand_zh='上虞';
UPDATE products SET brand_en='Yufan', brand_sw='Yufan' WHERE brand_zh='与凡';
UPDATE products SET brand_en='Shilin', brand_sw='Shilin' WHERE brand_zh='世林';
UPDATE products SET brand_en='Shiding', brand_sw='Shiding' WHERE brand_zh='世鼎';
UPDATE products SET brand_en='Dongjun', brand_sw='Dongjun' WHERE brand_zh='东君';
UPDATE products SET brand_en='Dongan', brand_sw='Dongan' WHERE brand_zh='东安';
UPDATE products SET brand_en='Donghong', brand_sw='Donghong' WHERE brand_zh='东宏';
UPDATE products SET brand_en='Dongyue', brand_sw='Dongyue' WHERE brand_zh='东岳';
UPDATE products SET brand_en='Donggong', brand_sw='Donggong' WHERE brand_zh='东工';
UPDATE products SET brand_en='Dongyue', brand_sw='Dongyue' WHERE brand_zh='东悦';
UPDATE products SET brand_en='Dongpeng', brand_sw='Dongpeng' WHERE brand_zh='东鹏';
UPDATE products SET brand_en='Dongbei', brand_sw='Dongbei' WHERE brand_zh='东贝';
UPDATE products SET brand_en='Dongming', brand_sw='Dongming' WHERE brand_zh='东明';
UPDATE products SET brand_en='Dongxiao', brand_sw='Dongxiao' WHERE brand_zh='东消';
UPDATE products SET brand_en='Chengqi', brand_sw='Chengqi' WHERE brand_zh='丞漆';
UPDATE products SET brand_en='Zhongjiao Ruihang', brand_sw='Zhongjiao Ruihang' WHERE brand_zh='中交瑞航';
UPDATE products SET brand_en='Zhongji Zhenying', brand_sw='Zhongji Zhenying' WHERE brand_zh='中冀振赢';
UPDATE products SET brand_en='Zhongli', brand_sw='Zhongli' WHERE brand_zh='中力';
UPDATE products SET brand_en='Zhonghe', brand_sw='Zhonghe' WHERE brand_zh='中和';
UPDATE products SET brand_en='Zhongda', brand_sw='Zhongda' WHERE brand_zh='中大';
UPDATE products SET brand_en='Zhongtian Dingsheng', brand_sw='Zhongtian Dingsheng' WHERE brand_zh='中天鼎盛';
UPDATE products SET brand_en='Zhongyu Seiko', brand_sw='Zhongyu Seiko' WHERE brand_zh='中宇精工';
UPDATE products SET brand_en='Zhongansheng', brand_sw='Zhongansheng' WHERE brand_zh='中安生';
UPDATE products SET brand_en='Zhongde Xinya', brand_sw='Zhongde Xinya' WHERE brand_zh='中德新亚';
UPDATE products SET brand_en='Zhongheng Lezhu', brand_sw='Zhongheng Lezhu' WHERE brand_zh='中恒乐筑';
UPDATE products SET brand_en='Zhongke', brand_sw='Zhongke' WHERE brand_zh='中科';
UPDATE products SET brand_en='Zhongxun', brand_sw='Zhongxun' WHERE brand_zh='中讯';
UPDATE products SET brand_en='Zhongcai', brand_sw='Zhongcai' WHERE brand_zh='中财';
UPDATE products SET brand_en='Zhongleite', brand_sw='Zhongleite' WHERE brand_zh='中雷特';
UPDATE products SET brand_en='Zhongzhen', brand_sw='Zhongzhen' WHERE brand_zh='中震';
UPDATE products SET brand_en='Fengguan', brand_sw='Fengguan' WHERE brand_zh='丰冠';
UPDATE products SET brand_en='Fenghuafeng', brand_sw='Fenghuafeng' WHERE brand_zh='丰华丰';
UPDATE products SET brand_en='Fengzhe', brand_sw='Fengzhe' WHERE brand_zh='丰哲';
UPDATE products SET brand_en='Fengde', brand_sw='Fengde' WHERE brand_zh='丰德';
UPDATE products SET brand_en='Fenglong Gaoke', brand_sw='Fenglong Gaoke' WHERE brand_zh='丰隆高科';
UPDATE products SET brand_en='Lishimei', brand_sw='Lishimei' WHERE brand_zh='丽施美';
UPDATE products SET brand_en='Jiujiu Fengji', brand_sw='Jiujiu Fengji' WHERE brand_zh='久久风机';
UPDATE products SET brand_en='Jiuxing', brand_sw='Jiuxing' WHERE brand_zh='久星';
UPDATE products SET brand_en='Jiurun Lihua', brand_sw='Jiurun Lihua' WHERE brand_zh='久润利华';
UPDATE products SET brand_en='Jiuyi', brand_sw='Jiuyi' WHERE brand_zh='久益';
UPDATE products SET brand_en='Lehua', brand_sw='Lehua' WHERE brand_zh='乐化';
UPDATE products SET brand_en='Lesiqi', brand_sw='Lesiqi' WHERE brand_zh='乐思琪';
UPDATE products SET brand_en='Leqing', brand_sw='Leqing' WHERE brand_zh='乐清';
UPDATE products SET brand_en='Legang', brand_sw='Legang' WHERE brand_zh='乐钢';
UPDATE products SET brand_en='Qiaoli', brand_sw='Qiaoli' WHERE brand_zh='乔立';
UPDATE products SET brand_en='Jiujia', brand_sw='Jiujia' WHERE brand_zh='九家';
UPDATE products SET brand_en='Jiuhui', brand_sw='Jiuhui' WHERE brand_zh='九辉';
UPDATE products SET brand_en='Jiulingsuojiguang', brand_sw='Jiulingsuojiguang' WHERE brand_zh='九零所';
UPDATE products SET brand_en='Jiubiao Jiguang', brand_sw='Jiubiao Jiguang' WHERE brand_zh='九骉极光';
UPDATE products SET brand_en='Shuchi', brand_sw='Shuchi' WHERE brand_zh='书驰';
UPDATE products SET brand_en='Yunxing', brand_sw='Yunxing' WHERE brand_zh='云星锚固';
UPDATE products SET brand_en='Hushida', brand_sw='Hushida' WHERE brand_zh='互视达';
UPDATE products SET brand_en='Wubao', brand_sw='Wubao' WHERE brand_zh='五宝';
UPDATE products SET brand_en='Wucai Xiongmao', brand_sw='Wucai Xiongmao' WHERE brand_zh='五彩熊猫';
UPDATE products SET brand_en='Yatai', brand_sw='Yatai' WHERE brand_zh='亚太';
UPDATE products SET brand_en='Yaanluo', brand_sw='Yaanluo' WHERE brand_zh='亚安罗';
UPDATE products SET brand_en='Yasuowang', brand_sw='Yasuowang' WHERE brand_zh='亚速旺';
UPDATE products SET brand_en='Hengxin Keji', brand_sw='Hengxin Keji' WHERE brand_zh='亨鑫科技';
UPDATE products SET brand_en='Jingtan', brand_sw='Jingtan' WHERE brand_zh='京坛';
UPDATE products SET brand_en='Jingkai', brand_sw='Jingkai' WHERE brand_zh='京开';
UPDATE products SET brand_en='Jingyang', brand_sw='Jingyang' WHERE brand_zh='京扬';
UPDATE products SET brand_en='Jingshui Yanshan', brand_sw='Jingshui Yanshan' WHERE brand_zh='京水燕山';
UPDATE products SET brand_en='Jingyuan', brand_sw='Jingyuan' WHERE brand_zh='京源';
UPDATE products SET brand_en='Jingsheng', brand_sw='Jingsheng' WHERE brand_zh='京生';
UPDATE products SET brand_en='Jingdu', brand_sw='Jingdu' WHERE brand_zh='京都';
UPDATE products SET brand_en='Jingshun', brand_sw='Jingshun' WHERE brand_zh='京顺';
UPDATE products SET brand_en='Jingbei Huayan', brand_sw='Jingbei Huayan' WHERE brand_zh='京北华燕';

-- ══════════════════════════════════════════════════════════
-- 五、标记 trans_meta 为 manual，防止翻译管道覆盖人工品牌翻译
-- ══════════════════════════════════════════════════════════
UPDATE products
SET trans_meta = (trans_meta::jsonb || '{"brand_en": "manual", "brand_sw": "manual"}'::jsonb)::json
WHERE brand_en IS NOT NULL AND brand_en != '';

COMMIT;
