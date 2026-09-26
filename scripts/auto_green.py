#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Daily Auto-Green & Tech Digest Generator
每天自动抓取 GitHub 热门开源项目、Hacker News 科技资讯与极客格言，
更新 README 看板与每日归档，并支持每天随机提交 1~5 次以点亮不同深浅的 GitHub 绿格子。
"""

import argparse
import datetime
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# 固定使用北京时间 (UTC+8)
BJT = datetime.timezone(datetime.timedelta(hours=8))

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "stats.json"
README_FILE = ROOT_DIR / "README.md"
ARCHIVES_DIR = ROOT_DIR / "archives"

README_START_MARKER = "<!-- AUTO-GREEN-START -->"
README_END_MARKER = "<!-- AUTO-GREEN-END -->"

# 精选极客与编程名言库（双语），确保无外部网络波动时依然高质量输出
QUOTES_POOL: List[Dict[str, str]] = [
    {
        "en": "Talk is cheap. Show me the code.",
        "zh": "空谈无益，亮出代码。",
        "author": "Linus Torvalds",
    },
    {
        "en": "Programs must be written for people to read, and only incidentally for machines to execute.",
        "zh": "程序首先是写给人看的，其次才是顺便让机器执行的。",
        "author": "Harold Abelson",
    },
    {
        "en": "Premature optimization is the root of all evil.",
        "zh": "过早的优化是万恶之源。",
        "author": "Donald Knuth",
    },
    {
        "en": "The best way to predict the future is to invent it.",
        "zh": "预测未来的最好方式就是亲手创造它。",
        "author": "Alan Kay",
    },
    {
        "en": "Simplicity is prerequisite for reliability.",
        "zh": "简单性是可靠性的先决条件。",
        "author": "Edsger W. Dijkstra",
    },
    {
        "en": "Any fool can write code that a computer can understand. Good programmers write code that humans can understand.",
        "zh": "任何傻瓜都能写出计算机能懂的代码，优秀的程序员写出人类能懂的代码。",
        "author": "Martin Fowler",
    },
    {
        "en": "First, solve the problem. Then, write the code.",
        "zh": "先解决问题，再动手写代码。",
        "author": "John Johnson",
    },
    {
        "en": "Make it work, make it right, make it fast.",
        "zh": "先让它跑起来，再让它变正确，最后让它变快。",
        "author": "Kent Beck",
    },
    {
        "en": "One of my most productive days was throwing away 1,000 lines of code.",
        "zh": "我最高效的一天，是删掉了 1000 行代码。",
        "author": "Ken Thompson",
    },
    {
        "en": "Controlling complexity is the essence of computer programming.",
        "zh": "控制复杂度是计算机编程的本质。",
        "author": "Brian Kernighan",
    },
    {
        "en": "Code is like humor. When you have to explain it, it’s bad.",
        "zh": "代码就像幽默，如果你必须解释它，那它就不够好。",
        "author": "Cory House",
    },
    {
        "en": "Debugging is twice as hard as writing the code in the first place.",
        "zh": "调试代码比写代码难两倍。",
        "author": "Brian Kernighan",
    },
]


def http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Any:
    """使用标准库发起 HTTP GET 请求并解析 JSON。"""
    req_headers = {
        "User-Agent": "GitHub-Auto-Green-Digest/1.0",
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_github_trending(now: datetime.datetime, limit: int = 5) -> List[Dict[str, Any]]:
    """抓取近期最热门的 GitHub 开源仓库（过去 7 天内创建且 Star 增长最快）。"""
    since_date = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    url = (
        f"https://api.github.com/search/repositories"
        f"?q=created:>{since_date}&sort=stars&order=desc&per_page={limit}"
    )
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        data = http_get_json(url, headers=headers, timeout=12)
        items = data.get("items", [])
        repos = []
        for item in items[:limit]:
            desc = (item.get("description") or "暂无描述").replace("\n", " ").replace("|", "\\|").strip()
            if len(desc) > 90:
                desc = desc[:87] + "..."
            repos.append(
                {
                    "name": item.get("full_name", "unknown/repo"),
                    "url": item.get("html_url", "https://github.com"),
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language") or "Markdown",
                    "description": desc,
                }
            )
        if repos:
            return repos
    except Exception as exc:
        print(f"[WARN] 获取 GitHub 热门仓库失败，使用兜底数据: {exc}")

    # 离线或限流时的兜底展示
    return [
        {
            "name": "torvalds/linux",
            "url": "https://github.com/torvalds/linux",
            "stars": 180000,
            "language": "C",
            "description": "Linux kernel source tree",
        },
        {
            "name": "python/cpython",
            "url": "https://github.com/python/cpython",
            "stars": 65000,
            "language": "Python",
            "description": "The Python programming language",
        },
    ]


def fetch_hacker_news(limit: int = 5) -> List[Dict[str, Any]]:
    """从 Hacker News 官方 API 获取当日热门技术资讯。"""
    try:
        top_ids = http_get_json(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        )
        stories = []
        for story_id in (top_ids or [])[: limit * 2]:
            if len(stories) >= limit:
                break
            item = http_get_json(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=6
            )
            if not item or item.get("type") != "story":
                continue
            title = (item.get("title") or "").strip()
            url = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            score = item.get("score", 0)
            if title:
                stories.append({"title": title, "url": url, "score": score, "id": story_id})
        if stories:
            return stories
    except Exception as exc:
        print(f"[WARN] 获取 Hacker News 资讯失败，使用兜底数据: {exc}")

    return [
        {
            "title": "Hacker News - Top Tech Stories",
            "url": "https://news.ycombinator.com/",
            "score": 100,
            "id": 1,
        }
    ]


def pick_daily_quote(now: datetime.datetime) -> Dict[str, str]:
    """根据日期与随机因子选取每日极客格言。"""
    idx = (now.toordinal() + random.randint(0, len(QUOTES_POOL) - 1)) % len(QUOTES_POOL)
    return QUOTES_POOL[idx]


def load_stats() -> Dict[str, Any]:
    """加载打卡统计数据。"""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "total_days": 0,
        "total_commits": 0,
        "current_streak": 0,
        "longest_streak": 0,
        "last_checkin_date": "",
        "last_updated": "",
        "history": [],
    }


def save_stats(stats: Dict[str, Any]) -> None:
    """保存打卡统计数据。"""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def update_stats_for_commit(
    stats: Dict[str, Any],
    now: datetime.datetime,
    commit_index: int,
    planned_commits: int,
    note: str,
) -> Dict[str, Any]:
    """更新统计数据（每次提交递增总提交数，跨天时递增打卡天数与连续天数）。"""
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S BJT")

    last_date = stats.get("last_checkin_date", "")
    if last_date != today_str:
        stats["total_days"] = int(stats.get("total_days", 0)) + 1
        # 检查是否连续打卡（昨天打过卡则连续天数+1，否则重置为1）
        yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if last_date == yesterday_str:
            stats["current_streak"] = int(stats.get("current_streak", 0)) + 1
        else:
            stats["current_streak"] = 1

        if stats["current_streak"] > int(stats.get("longest_streak", 0)):
            stats["longest_streak"] = stats["current_streak"]
        stats["last_checkin_date"] = today_str

    stats["total_commits"] = int(stats.get("total_commits", 0)) + 1
    stats["last_updated"] = time_str

    history: List[Dict[str, Any]] = stats.get("history", [])
    history.insert(
        0,
        {
            "timestamp": time_str,
            "date": today_str,
            "step": f"{commit_index}/{planned_commits}",
            "note": note,
        },
    )
    # 仅保留最近 15 条打卡记录
    stats["history"] = history[:15]
    return stats


def render_archive_markdown(
    now: datetime.datetime,
    quote: Dict[str, str],
    repos: Optional[List[Dict[str, Any]]] = None,
    stories: Optional[List[Dict[str, Any]]] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> str:
    """生成每日归档 Markdown 内容。"""
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S BJT")

    lines = [
        f"# 📅 每日技术早报与打卡归档 ({today_str})",
        "",
        f"> 更新时间：`{time_str}`",
        "",
        "## 💡 每日极客格言",
        "",
        f"> *\"{quote['en']}\"*  ",
        f"> 「{quote['zh']}」 —— **{quote['author']}**",
        "",
    ]

    if repos is not None:
        lines.extend(
            [
                "## 🔥 GitHub 近期飙升开源项目",
                "",
                "| 项目名称 | 主要语言 | ⭐ Stars | 项目简介 |",
                "| :--- | :---: | :---: | :--- |",
            ]
        )
        for repo in repos:
            lines.append(
                f"| [{repo['name']}]({repo['url']}) | `{repo['language']}` | **{repo['stars']}** | {repo['description']} |"
            )
        lines.append("")

    if stories is not None:
        lines.extend(["## 📰 Hacker News 热门科技资讯", ""])
        for idx, story in enumerate(stories, start=1):
            lines.append(
                f"{idx}. [{story['title']}]({story['url']}) *(🔥 {story['score']} points)*"
            )
        lines.append("")

    if stats is not None:
        lines.extend(
            [
                "## 📊 当日打卡状态",
                "",
                f"- **累计打卡天数**：`{stats.get('total_days', 1)}` 天",
                f"- **当前连续打卡**：`{stats.get('current_streak', 1)}` 天",
                f"- **累计自动提交**：`{stats.get('total_commits', 1)}` 次",
                "",
            ]
        )

    return "\n".join(lines)


def render_readme_dashboard(
    now: datetime.datetime,
    stats: Dict[str, Any],
    quote: Dict[str, str],
    repos: List[Dict[str, Any]],
    stories: List[Dict[str, Any]],
    planned_commits: int,
) -> str:
    """生成嵌入在 README.md 中的动态技术看板内容。"""
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S BJT")
    archive_rel_path = f"archives/{now.strftime('%Y-%m')}/{today_str}.md"

    lines = [
        "### 📊 自动点绿打卡统计 (Auto-Green Dashboard)",
        "",
        f"![累计打卡天数](https://img.shields.io/badge/%E7%B4%AF%E8%AE%A1%E6%89%93%E5%8D%A1-{stats.get('total_days', 1)}%20%E5%A4%A9-2ea44f?style=flat-square) "
        f"![连续打卡](https://img.shields.io/badge/%E8%BF%9E%E7%BB%AD%E6%89%93%E5%8D%A1-{stats.get('current_streak', 1)}%20%E5%A4%A9-39d353?style=flat-square) "
        f"![累计提交次数](https://img.shields.io/badge/%E7%B4%AF%E8%AE%A1%E6%8F%90%E4%BA%A4-{stats.get('total_commits', 1)}%20%E6%AC%A1-26a641?style=flat-square) "
        f"![今日提交目标](https://img.shields.io/badge/%E4%BB%8A%E6%97%A5%E9%9A%8F%E6%9C%BA%E6%8F%90%E4%BA%A4-{planned_commits}%20%E6%AC%A1-006d32?style=flat-square)",
        "",
        f"- 🕒 **最后更新时间**：`{time_str}`",
        f"- 📂 **今日完整归档**：[{archive_rel_path}]({archive_rel_path})",
        "",
        "---",
        "",
        "### 💡 每日极客格言 (Daily Dev Quote)",
        "",
        f"> *\"{quote['en']}\"*  ",
        f"> 「{quote['zh']}」  ",
        f"> —— **{quote['author']}**",
        "",
        "---",
        "",
        "### 🔥 GitHub 近期热门飙升项目 (Trending Repos)",
        "",
        "| 开源项目 | 语言 | ⭐ Stars | 简介 |",
        "| :--- | :---: | :---: | :--- |",
    ]

    for repo in repos:
        lines.append(
            f"| [**{repo['name']}**]({repo['url']}) | `{repo['language']}` | `{repo['stars']}` | {repo['description']} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "### 📰 Hacker News 每日科技热榜 (Top Tech News)",
            "",
        ]
    )

    for idx, story in enumerate(stories, start=1):
        lines.append(
            f"{idx}. [{story['title']}]({story['url']}) `🔥 {story['score']} pts`"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "### 📝 最近打卡记录 (Recent Check-ins)",
            "",
            "| 时间 (BJT) | 进度 | 提交说明 |",
            "| :--- | :---: | :--- |",
        ]
    )

    for item in stats.get("history", [])[:6]:
        lines.append(
            f"| `{item.get('timestamp', '')}` | `{item.get('step', '1/1')}` | {item.get('note', '')} |"
        )

    return "\n".join(lines)


def update_readme_file(dashboard_md: str) -> None:
    """将动态看板写入 README.md 的标记区间内。"""
    replacement = f"{README_START_MARKER}\n{dashboard_md}\n{README_END_MARKER}"
    if README_FILE.exists():
        content = README_FILE.read_text(encoding="utf-8")
        pattern = re.compile(
            re.escape(README_START_MARKER) + r".*?" + re.escape(README_END_MARKER),
            re.DOTALL,
        )
        if pattern.search(content):
            new_content = pattern.sub(lambda _: replacement, content)
        else:
            new_content = content.rstrip() + "\n\n" + replacement + "\n"
    else:
        new_content = f"# 🟩 GitHub Auto-Green\n\n{replacement}\n"

    README_FILE.write_text(new_content, encoding="utf-8")


def run_git_commit(message: str) -> bool:
    """执行 git add 与 git commit，创建一个真实的 Git 提交记录。"""
    try:
        subprocess.run(["git", "add", "-A"], cwd=ROOT_DIR, check=True)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        if not status.stdout.strip():
            print(f"[INFO] 无文件变动，跳过提交: {message}")
            return False

        subprocess.run(["git", "commit", "-m", message], cwd=ROOT_DIR, check=True)
        print(f"[OK] 已创建提交: {message}")
        return True
    except Exception as exc:
        print(f"[ERROR] Git 提交失败: {exc}")
        return False


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="GitHub 每日自动点绿与技术早报生成脚本"
    )
    parser.add_argument(
        "--min-commits",
        type=int,
        default=1,
        help="单日最少提交次数（默认: 1）",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=5,
        help="单日最多提交次数（默认: 5）",
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=0,
        help="指定固定提交次数（若 > 0 则忽略随机范围）",
    )
    parser.add_argument(
        "--auto-commit",
        action="store_true",
        help="是否自动执行 git add 和 git commit（用于 GitHub Actions）",
    )
    args = parser.parse_args()

    if args.commits > 0:
        planned_commits = max(1, min(args.commits, 10))
    else:
        low = max(1, args.min_commits)
        high = max(low, args.max_commits)
        planned_commits = random.randint(low, high)

    now = datetime.datetime.now(BJT)
    today_str = now.strftime("%Y-%m-%d")
    archive_file = ARCHIVES_DIR / now.strftime("%Y-%m") / f"{today_str}.md"
    archive_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] 今日计划生成提交次数: {planned_commits} 次")

    # 抓取今日资讯与数据
    quote = pick_daily_quote(now)
    repos = fetch_github_trending(now, limit=5)
    stories = fetch_hacker_news(limit=5)
    stats = load_stats()

    # 定义最多 5 个渐进式提交阶段，保证每次提交都有真实且有意义的改动
    stage_definitions = [
        (
            f"chore(checkin): update daily check-in stats for {today_str}",
            "更新每日打卡计数与连续活跃状态",
        ),
        (
            f"docs(quote): add daily developer quote ({today_str})",
            "收录今日极客格言与每日归档",
        ),
        (
            f"docs(trending): sync GitHub hot repositories ({today_str})",
            "同步 GitHub 近期热门飙升开源项目",
        ),
        (
            f"docs(news): sync Hacker News top tech stories ({today_str})",
            "同步 Hacker News 热门技术资讯",
        ),
        (
            f"docs(readme): refresh daily tech digest dashboard ({today_str})",
            "更新 README 每日科技看板与徽章",
        ),
    ]

    if not args.auto_commit:
        # 本地预览模式：直接一次性更新所有文件，不执行 git commit
        stats = update_stats_for_commit(
            stats, now, 1, 1, "同步 GitHub 热门项目、Hacker News 资讯与每日格言"
        )
        save_stats(stats)
        archive_md = render_archive_markdown(now, quote, repos, stories, stats)
        archive_file.write_text(archive_md, encoding="utf-8")
        dashboard_md = render_readme_dashboard(
            now, stats, quote, repos, stories, planned_commits
        )
        update_readme_file(dashboard_md)
        print("[OK] 已更新 data/stats.json、今日归档及 README.md（未执行 git commit）。")
        return

    # 自动提交模式：分阶段执行，产生 planned_commits 个真实的 Git commit
    for i in range(1, planned_commits + 1):
        step_now = datetime.datetime.now(BJT) + datetime.timedelta(seconds=i)
        is_last_step = i == planned_commits

        if is_last_step:
            commit_msg, note = stage_definitions[-1]
        else:
            commit_msg, note = stage_definitions[min(i - 1, len(stage_definitions) - 2)]

        # 每次提交都更新 stats.json
        stats = update_stats_for_commit(stats, step_now, i, planned_commits, note)
        save_stats(stats)

        # 根据当前阶段逐步丰富归档与 README，最后一步确保所有内容完整写入
        if is_last_step:
            archive_md = render_archive_markdown(
                step_now, quote, repos, stories, stats
            )
            archive_file.write_text(archive_md, encoding="utf-8")
            dashboard_md = render_readme_dashboard(
                step_now, stats, quote, repos, stories, planned_commits
            )
            update_readme_file(dashboard_md)
        elif i == 2:
            archive_md = render_archive_markdown(step_now, quote, None, None, stats)
            archive_file.write_text(archive_md, encoding="utf-8")
        elif i == 3:
            archive_md = render_archive_markdown(step_now, quote, repos, None, stats)
            archive_file.write_text(archive_md, encoding="utf-8")
        elif i == 4:
            archive_md = render_archive_markdown(
                step_now, quote, repos, stories, stats
            )
            archive_file.write_text(archive_md, encoding="utf-8")

        run_git_commit(commit_msg)
        if not is_last_step:
            time.sleep(1)


if __name__ == "__main__":
    main()
