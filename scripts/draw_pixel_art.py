#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 贡献墙像素图案绘制工具 (7×35 Pixel Art Generator)
从 2026 年 1 月第一个完整周 (2026-01-04) 开始点亮加粗像素艺术字：
H E L L O W
"""

from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent

# 7 行高度的加粗像素字模 (HELLOW)
# '.' = 0 次提交（留白背景）
# '#' = 10 次提交（深绿实心主体）
BLOCKS: List[Dict[str, object]] = [
    {
        "name": "H",
        "gap_after": 1,
        "grid": [
            "##.##",
            "##.##",
            "##.##",
            "#####",
            "##.##",
            "##.##",
            "##.##",
        ],
    },
    {
        "name": "E",
        "gap_after": 1,
        "grid": [
            "#####",
            "##...",
            "##...",
            "####.",
            "##...",
            "##...",
            "#####",
        ],
    },
    {
        "name": "L",
        "gap_after": 1,
        "grid": [
            "##..",
            "##..",
            "##..",
            "##..",
            "##..",
            "####",
            "####",
        ],
    },
    {
        "name": "L",
        "gap_after": 1,
        "grid": [
            "##..",
            "##..",
            "##..",
            "##..",
            "##..",
            "####",
            "####",
        ],
    },
    {
        "name": "O",
        "gap_after": 1,
        "grid": [
            ".###.",
            "##.##",
            "##.##",
            "##.##",
            "##.##",
            "##.##",
            ".###.",
        ],
    },
    {
        "name": "W",
        "gap_after": 0,
        "grid": [
            "##...##",
            "##...##",
            "##.#.##",
            "##.#.##",
            "#######",
            ".##.##.",
            ".#...#.",
        ],
    },
]


def build_canvas() -> List[str]:
    """拼接 7 行 × 35 列的完整 HELLOW 像素画布。"""
    rows = ["" for _ in range(7)]
    for block in BLOCKS:
        grid: List[str] = block["grid"]  # type: ignore
        gap: int = block["gap_after"]  # type: ignore
        for r in range(7):
            rows[r] += grid[r] + ("." * gap)
    return rows


def main() -> None:
    canvas = build_canvas()
    num_cols = len(canvas[0])
    print(f"Canvas size: 7 rows x {num_cols} columns")
    for r in canvas:
        print(r.replace(".", "⬜").replace("#", "🌲"))


if __name__ == "__main__":
    main()
