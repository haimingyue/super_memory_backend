from __future__ import annotations

import re

from app.services.llm_service import llm_service

# 规则词典：概念/术语 -> 可见对象
RULE_VISUAL_DICT = {
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
    "启动": "点火按钮",
    "规划": "施工蓝图",
    "执行": "传送带",
    "监控": "监视屏",
    "收尾": "归档盒",
}

FALLBACK_OBJECTS = ["锤子", "雨伞", "齿轮", "望远镜", "磁铁", "小火车", "喇叭", "手电筒", "纸箱"]
ABSTRACT_WORDS = {
    "能力",
    "原则",
    "机制",
    "系统",
    "模型",
    "过程",
    "流程",
    "策略",
    "方法",
    "概念",
    "定义",
    "思想",
    "理论",
    "架构",
    "优化",
    "管理",
    "质量",
    "效率",
}
ACTION_WORDS = {
    "推",
    "拉",
    "扔",
    "举",
    "拖",
    "喷",
    "点亮",
    "卷",
    "挂",
    "变",
    "贴",
    "砸",
    "拧",
    "甩",
    "吸",
    "夹",
    "装",
    "搬",
    "拽",
    "弹",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip()


def _strip_prefix(line: str) -> str:
    s = line or ""
    s = re.sub(r"^\s*(?:\d+[\.、]|[①②③④⑤⑥⑦⑧⑨⑩]|[(（]\d+[)）]|[一二三四五六七八九十]+、|[-*])\s*", "", s)
    s = s.strip()
    if "：" in s:
        return s.split("：", 1)[0].strip()
    if ":" in s:
        return s.split(":", 1)[0].strip()
    return s


def _is_concrete_word(text: str) -> bool:
    t = _normalize(text)
    if not t:
        return False
    if any(word in t for word in ABSTRACT_WORDS):
        return False
    concrete_suffix = ("器", "机", "箱", "锁", "柜", "门", "车", "灯", "图标", "按钮", "牌", "桥", "杯", "伞")
    if t in RULE_VISUAL_DICT.values():
        return True
    if any(t.endswith(suf) for suf in concrete_suffix):
        return True
    if len(t) <= 6 and re.search(r"[\u4e00-\u9fff]", t):
        return True
    return False


def _rule_map_visual(source: str, idx: int) -> str:
    norm = _normalize(source)
    for key, visual in RULE_VISUAL_DICT.items():
        if key in norm or norm in key:
            return visual

    if re.fullmatch(r"[A-Za-z]{2,}", source or ""):
        return f"{source.upper()}牌子"

    base = re.sub(r"(层|模型|系统|过程组|过程|步骤|方法|策略)$", "", source or "").strip()
    if base and _is_concrete_word(f"{base}道具"):
        return f"{base}道具"

    return FALLBACK_OBJECTS[idx % len(FALLBACK_OBJECTS)]


def _llm_map_visual(question: str, source: str, content_type: str, primary_method: str, idx: int) -> str:
    try:
        visual = llm_service.generate_visual_anchor(
            question=question,
            source=source,
            content_type=content_type,
            primary_method=primary_method,
        )
        if visual and _is_concrete_word(visual):
            return visual
    except Exception:
        pass
    return FALLBACK_OBJECTS[idx % len(FALLBACK_OBJECTS)]


def _build_hook(index: int, hook_system: str) -> str | None:
    if hook_system == "none_hooks":
        return None
    if hook_system == "number_hooks":
        return str(index)
    if hook_system == "alphabet_hooks":
        return chr(ord("A") + ((index - 1) % 26))
    if hook_system == "date_hooks":
        return f"T{index}"
    if hook_system == "space_hooks":
        return f"位置{index}"
    return None


def _build_function_hint(content_type: str, primary_method: str) -> str:
    if content_type == "timeline":
        return "timepoint"
    if content_type == "compare_contrast":
        return "contrast"
    if primary_method == "peg_method":
        return "indexed_slot"
    return "step"


def build_visual_anchors(
    question: str,
    answer_lines: list[str],
    content_type: str,
    primary_method: str,
    hook_system: str = "none_hooks",
    secondary_methods: list[str] | None = None,
) -> list[dict]:
    anchors: list[dict] = []
    used_visuals: set[str] = set()
    use_substitute = "substitute_word_method" in (secondary_methods or [])

    for idx, raw in enumerate(answer_lines):
        source = _strip_prefix(raw)
        if not source:
            continue

        visual = _rule_map_visual(source, idx)
        # 规则映射无效或过抽象时，回退到 LLM
        if not visual or (visual == source and not _is_concrete_word(source)) or not _is_concrete_word(visual):
            visual = _llm_map_visual(question, source, content_type, primary_method, idx)

        # substitute_word_method：将抽象词进一步具象化
        if use_substitute and (not _is_concrete_word(visual) or _is_concrete_word(source) is False):
            base = re.sub(r"(系统|模型|策略|方法|流程|机制|概念|定义)$", "", source).strip()
            visual = f"{base or source or '概念'}道具"

        # 保证 visual 可区分，避免重复导致联想冲突
        if visual in used_visuals:
            visual = f"{visual}{idx + 1}"
        used_visuals.add(visual)

        abstract_level = "low" if _is_concrete_word(visual) else "high"
        anchors.append(
            {
                "index": len(anchors) + 1,
                "source": source,
                "visual": visual,
                "hook": _build_hook(len(anchors) + 1, hook_system),
                "functionHint": _build_function_hint(content_type, primary_method),
                "abstractLevel": abstract_level,
            }
        )

    if not anchors:
        anchors.append(
            {
                "index": 1,
                "source": "默认要点",
                "visual": FALLBACK_OBJECTS[0],
                "hook": _build_hook(1, hook_system),
                "functionHint": _build_function_hint(content_type, primary_method),
                "abstractLevel": "low",
            }
        )

    return anchors[:9]


def validate_visual_anchors(anchors: list[dict]) -> list[str]:
    issues: list[str] = []
    for anchor in anchors:
        source = str(anchor.get("source", "")).strip()
        visual = str(anchor.get("visual", "")).strip()
        idx = anchor.get("index")
        if not visual:
            issues.append(f"anchor[{idx}] visual 为空")
            continue
        if visual == source and not _is_concrete_word(source):
            issues.append(f"anchor[{idx}] visual 与 source 相同且 source 抽象")
        if not _is_concrete_word(visual):
            issues.append(f"anchor[{idx}] visual 不够具体")
    return issues


def validate_imagery_lines(imagery: list[str], anchors: list[dict]) -> list[str]:
    issues: list[str] = []
    anchor_visuals = [str(a.get("visual", "")).strip() for a in anchors if str(a.get("visual", "")).strip()]
    for idx, line in enumerate(imagery):
        text = (line or "").strip()
        if not text:
            issues.append(f"imagery[{idx + 1}] 为空")
            continue
        has_action = any(action in text for action in ACTION_WORDS)
        has_object = any(v in text for v in anchor_visuals) or _is_concrete_word(text)
        if not has_action or not has_object:
            issues.append(f"imagery[{idx + 1}] 缺少具体物体或动作")
    return issues
