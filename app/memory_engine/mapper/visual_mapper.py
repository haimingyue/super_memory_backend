from __future__ import annotations

import re

# 领域视觉化词典：概念 -> 可见物体
VISUAL_DICT = {
    "物理层": "电线",
    "数据链路层": "网线",
    "网络层": "路由器",
    "传输层": "快递箱",
    "会话层": "对讲机",
    "表示层": "翻译机",
    "应用层": "APP图标",
    "缓存": "冰箱",
    "数据库": "档案柜",
    "队列": "排队口",
    "线程": "传送带",
    "进程": "工厂",
    "加密": "密码锁",
    "解密": "钥匙",
    "路由": "导航仪",
    "IP": "门牌号",
    "TCP": "挂号信",
    "UDP": "纸飞机",
}

FALLBACK_OBJECTS = ["锤子", "雨伞", "齿轮", "望远镜", "磁铁", "小火车", "喇叭", "手电筒", "纸箱"]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _pick_visual(concept: str, idx: int) -> str:
    norm = _normalize(concept)
    for key, visual in VISUAL_DICT.items():
        if key in norm or norm in key:
            return visual

    # 英文缩写和单词
    if re.fullmatch(r"[A-Za-z]{2,}", concept or ""):
        return f"{concept.upper()}牌子"

    base = re.sub(r"(层|模型|系统|过程组|过程|步骤)$", "", concept).strip()
    if base:
        return f"{base}道具"

    return FALLBACK_OBJECTS[idx % len(FALLBACK_OBJECTS)]


def map_visual_anchors(question: str, concepts: list[str]) -> list[str]:
    anchors: list[str] = []
    for idx, concept in enumerate(concepts):
        anchor = _pick_visual(concept, idx)
        anchors.append(anchor)

    # 去重并保序
    deduped: list[str] = []
    for a in anchors:
        if a not in deduped:
            deduped.append(a)

    if len(deduped) < 3:
        while len(deduped) < 3:
            deduped.append(FALLBACK_OBJECTS[len(deduped) % len(FALLBACK_OBJECTS)])

    return deduped[:9]
