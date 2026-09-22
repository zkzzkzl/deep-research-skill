#!/usr/bin/env python3
"""深度检索输出结构校验。

用法:
  python -X utf8 verify_report.py <报告文件.md>
  cat 报告.md | python -X utf8 verify_report.py

校验简洁档或报告档：
  - 简洁档：结论、来源、发布日期和核验状态。
  - 报告档：检索结论、证据与来源、来源分歧、核验状态、未覆盖范围。
  - 报告档证据表每行必须包含来源 URL。
  - 报告档证据表表头必须是规定的六列。
  - 结论必须标记为事实、来源观点或推断。

退出码: 0=通过; 1=有问题; 2=输入不像检索输出。
本脚本只读，不写入、不修改任何文件。
"""
from __future__ import annotations

import argparse
import re
import sys


HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
TABLE_SEP_RE = re.compile(r"^\|[\s:|\-]+\|$")
DATE_RE = re.compile(r"(?:19|20)\d{2}-\d{2}-\d{2}")
REPORT_SECTIONS = (
    ("检索结论", "Research Findings"),
    ("证据与来源", "Evidence and Sources"),
    ("来源分歧", "Source Disagreements"),
    ("核验状态", "Verification Status"),
    ("未覆盖范围", "Uncovered Scope"),
)
REPORT_HEADINGS = tuple(" / ".join(group) for group in REPORT_SECTIONS)
VERIFY_LABELS = (
    "已核实", "依据有限", "未验证", "存在分歧",
    "Verified", "Limited evidence", "Unverified", "Conflicting",
)
CLAIM_TYPES = ("事实", "来源观点", "推断", "Fact", "Source view", "Inference")
EVIDENCE_COLUMNS = ("#", "事实", "数值/要点", "来源与完整 URL", "发布日期", "证据类型")
EVIDENCE_COLUMNS_EN = (
    "#", "Fact", "Value/Key point", "Source and Full URL",
    "Publication Date", "Evidence Type",
)


def split_cells(row):
    """拆分 markdown 表格行；去掉首尾竖线，单元格去空白。"""
    text = row.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip() for cell in text.split("|")]


def same_columns(actual, expected):
    """比较列名，忽略空格差异。"""
    def squeeze(cells):
        return [re.sub(r"\s+", "", cell) for cell in cells]

    return squeeze(actual) == squeeze(expected)


def contains_label(text, labels):
    folded = text.casefold()
    for label in labels:
        if any("\u4e00" <= char <= "\u9fff" for char in label):
            if label in text:
                return True
            continue
        pattern = r"(?<![a-z])" + re.escape(label.casefold()) + r"(?![a-z])"
        if re.search(pattern, folded):
            return True
    return False


def find_heading(lines, keywords):
    if isinstance(keywords, str):
        keywords = (keywords,)
    folded_keywords = tuple(keyword.casefold() for keyword in keywords)
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = match.group(2).casefold()
        if any(keyword in heading for keyword in folded_keywords):
            return index
    return None


def section_lines(lines, heading, next_heading):
    start = find_heading(lines, heading)
    if start is None:
        return []
    end = next_heading if next_heading is not None else len(lines)
    return [line for line in lines[start + 1:end] if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="深度检索输出结构校验（只读）")
    parser.add_argument("report_file", nargs="?", help="Markdown 文件；缺省读取 stdin")
    args = parser.parse_args()

    if args.report_file:
        try:
            with open(args.report_file, encoding="utf-8-sig") as handle:
                text = handle.read()
        except OSError as exc:
            print(f"无法读取输入文件: {exc}")
            return 2
        source = args.report_file
    else:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        text = sys.stdin.read()
        source = "(stdin)"

    lines = text.splitlines()
    failures = []
    hints = []

    print("深度检索输出校验 · deep-research-skill")
    print(f"输入: {source}")
    print(f"行数: {len(lines)}")
    print()

    has_heading = any(HEADING_RE.match(line) for line in lines)
    has_table = any(line.lstrip().startswith("|") for line in lines)
    report_mode = has_heading or has_table

    if not any(line.strip() for line in lines):
        print("输入为空，不像检索输出。")
        return 2

    if report_mode:
        positions = []
        missing = []
        for aliases in REPORT_SECTIONS:
            position = find_heading(lines, aliases)
            if position is None:
                missing.append(" / ".join(aliases))
            else:
                positions.append((aliases, position))
        if missing:
            failures.append((
                "1. 报告骨架",
                f"缺少规定小节：{'、'.join(missing)}；应为 {' → '.join(REPORT_HEADINGS)}",
            ))
        else:
            ordered = [aliases for aliases, _ in positions]
            if ordered != list(REPORT_SECTIONS):
                failures.append((
                    "1. 报告骨架",
                    f"小节顺序错误：{' → '.join(' / '.join(group) for group in ordered)}；应为 {' → '.join(REPORT_HEADINGS)}",
                ))

        conclusion_lines = section_lines(
            lines,
            REPORT_SECTIONS[0],
            find_heading(lines, REPORT_SECTIONS[1]),
        )
        claim_lines = [
            line for line in conclusion_lines
            if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", line)
        ]
        if not claim_lines:
            failures.append((
                "2. 检索结论",
                "「检索结论」中没有可识别的结论条目",
            ))
        else:
            missing_types = [
                line.strip()
                for line in claim_lines
                if not contains_label(line, CLAIM_TYPES)
            ]
            if missing_types:
                failures.append((
                    "2. 结论类型",
                    f"以下结论未标注事实、来源观点或推断：{missing_types[0][:80]}",
                ))
            missing_verify = [
                line.strip()
                for line in claim_lines
                if not contains_label(line, VERIFY_LABELS)
            ]
            if missing_verify:
                failures.append((
                    "3. 核验状态",
                    f"以下结论未标注核验状态：{missing_verify[0][:80]}",
                ))

        evidence_pos = find_heading(lines, REPORT_SECTIONS[1])
        if evidence_pos is not None:
            evidence_end = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if HEADING_RE.match(line) and index > evidence_pos
                ),
                len(lines),
            )
            evidence_rows = []
            header_cells = []
            in_table = False
            for index in range(evidence_pos + 1, evidence_end):
                stripped = lines[index].lstrip()
                if stripped.startswith("|") and TABLE_SEP_RE.match(stripped):
                    in_table = True
                    continue
                if not stripped.startswith("|"):
                    continue
                if in_table:
                    evidence_rows.append((index + 1, lines[index]))
                else:
                    header_cells = split_cells(lines[index])
            if header_cells and not (
                same_columns(header_cells, EVIDENCE_COLUMNS)
                or same_columns(header_cells, EVIDENCE_COLUMNS_EN)
            ):
                failures.append((
                    "4. 证据表列名",
                    "表头为「" + " | ".join(header_cells) + "」；应为中文表头「"
                    + " | ".join(EVIDENCE_COLUMNS)
                    + "」或英文表头「"
                    + " | ".join(EVIDENCE_COLUMNS_EN)
                    + "」（见 output-contract.md 第二节）",
                ))
            if not evidence_rows:
                failures.append((
                    "4. 证据表",
                    "「证据与来源」中没有可识别的数据行",
                ))
            else:
                missing_urls = [
                    line_no
                    for line_no, row in evidence_rows
                    if "http" not in row
                ]
                if missing_urls:
                    failures.append((
                        "4. 证据表",
                        f"第 {missing_urls} 行没有来源 URL",
                    ))
    else:
        source_lines = [
            line.strip()
            for line in lines
            if re.match(r"^(来源[:：]|source\s*:)", line.strip(), re.IGNORECASE)
        ]
        verify_lines = [
            line.strip()
            for line in lines
            if re.match(r"^(核验[:：]|verification\s*:)", line.strip(), re.IGNORECASE)
        ]

        if not source_lines:
            failures.append((
                "1. 来源",
                "简洁档缺少「来源：」行",
            ))
        else:
            source_text = " ".join(source_lines)
            if "http" not in source_text and "无公开链接" not in source_text and "no public link" not in source_text.casefold():
                failures.append((
                    "1. 来源",
                    "来源行没有 URL；确无公开链接时必须说明原因",
                ))
            if not DATE_RE.search(source_text):
                failures.append((
                    "2. 发布日期",
                    "来源行缺少 YYYY-MM-DD 格式的发布日期",
                ))

        if not verify_lines:
            failures.append((
                "3. 核验状态",
                "简洁档缺少「核验：」行",
            ))
        elif not any(label in " ".join(verify_lines) for label in VERIFY_LABELS):
            failures.append((
                "3. 核验状态",
                f"核验状态应为：{'、'.join(VERIFY_LABELS)}",
            ))

    link_status_lines = [
        line.strip()
        for line in lines
        if re.match(r"^(链接状态[:：]|link status\s*:)", line.strip(), re.IGNORECASE)
    ]
    for line in link_status_lines:
        if "http" not in line and "无" not in line:
            failures.append((
                "5. 链接状态",
                f"链接状态说明缺少 URL 或明确结论：{line[:80]}",
            ))

    if not link_status_lines:
        hints.append("未展示链接状态；普通输出允许省略，但无法确认时应在内部记录")

    for label, message in failures:
        print(f"[失败] {label}：{message}")
    for message in hints:
        print(f"[提示] {message}")
    print()

    if failures:
        print(f"校验结论: 不通过（失败 {len(failures)} 项，退出码 1）")
        return 1

    print(f"校验结论: 通过（提示 {len(hints)} 项，退出码 0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
