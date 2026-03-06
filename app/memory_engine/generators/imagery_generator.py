from __future__ import annotations

ACTION_POOL = [
    "缠住",
    "拖着",
    "举起",
    "喷出",
    "吸走",
    "点亮",
    "推着",
    "卷走",
    "挂满",
    "变成",
]
SCENE_SUFFIX = ["地板震动。", "天花板发亮。", "全场在尖叫。", "墙面被点燃。", "空气都在抖。", "灯牌狂闪。"]
FORBIDDEN_WORDS = {"撞"}


def _line_limit(sentence: str, max_len: int = 20) -> str:
    s = sentence.strip()
    return s if len(s) <= max_len else s[:max_len]


def _validate_line(line: str) -> bool:
    if any(w in line for w in FORBIDDEN_WORDS):
        return False
    # 至少含一个动作词
    if not any(v in line for v in ACTION_POOL):
        return False
    return True


def _make_link_events(points: list[str]) -> list[str]:
    events: list[str] = []
    for idx in range(len(points) - 1):
        a = points[idx]
        b = points[idx + 1]
        v = ACTION_POOL[idx % len(ACTION_POOL)]
        suffix = SCENE_SUFFIX[idx % len(SCENE_SUFFIX)]
        line = f"{a}{v}{b}，{suffix}"
        events.append(_line_limit(line, 20))
    return events


def _make_peg_events(hooks: list[str], points: list[str]) -> list[str]:
    events: list[str] = []
    for idx, point in enumerate(points):
        hook = hooks[idx] if idx < len(hooks) else f"钩子{idx + 1}"
        v = ACTION_POOL[idx % len(ACTION_POOL)]
        suffix = SCENE_SUFFIX[idx % len(SCENE_SUFFIX)]
        line = f"{hook}{v}{point}，{suffix}"
        events.append(_line_limit(line, 20))
    return events


def _make_substitute_events(points: list[str]) -> list[str]:
    events: list[str] = []
    for idx, point in enumerate(points):
        v = ACTION_POOL[idx % len(ACTION_POOL)]
        suffix = SCENE_SUFFIX[idx % len(SCENE_SUFFIX)]
        line = f"{point}道具会{v}你，{suffix}"
        events.append(_line_limit(line, 20))
    return events


def _make_timeline_events(hooks: list[str], points: list[str]) -> list[str]:
    events: list[str] = []
    for idx, point in enumerate(points):
        t = hooks[idx] if idx < len(hooks) else f"时间{idx + 1}"
        v = ACTION_POOL[idx % len(ACTION_POOL)]
        suffix = SCENE_SUFFIX[idx % len(SCENE_SUFFIX)]
        line = f"{t}{v}{point}，{suffix}"
        events.append(_line_limit(line, 20))
    return events


def generate_imagery(method: str, hooks: list[str], keywords: list[str]) -> list[str]:
    points = (keywords or ["锚点A", "锚点B", "锚点C"])[:9]

    if method == "peg_method":
        imagery = _make_peg_events(hooks, points)
    elif method == "timeline_method":
        imagery = _make_timeline_events(hooks, points)
    elif method == "substitute_method":
        imagery = _make_substitute_events(points)
    else:
        imagery = _make_link_events(points)

    validated = [line for line in imagery if _validate_line(line)]
    if len(validated) < 5:
        validated.extend(
            [
                "道具突然变大并推着你跑。",
                "整条路线亮起并卷走云朵。",
                "最后一个道具点亮终点牌。",
            ]
        )
    validated = validated[:9]
    validated.append("现在闭上眼睛想象 5 秒")
    return validated[:10]
