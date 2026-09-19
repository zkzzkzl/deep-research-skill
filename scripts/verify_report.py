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
REPORT_HEADINGS = ("检索结论", "证据与来源", "来源分歧", "核验状态", "未覆盖范围")
VERIFY_LABELS = ("已核实", "依据有限", "未验证", "存在分歧")
CLAIM_TYPES = ("事实", "来源观点", "推断")
EVIDENCE_COLUMNS = ("#", "事实", "数值/要点", "来源与完整 URL", "发布日期", "证据类型")


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


def find_heading(lines, keyword):
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match and keyword in match.group(2):
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
        for heading in REPORT_HEADINGS:
            position = find_heading(lines, heading)
            if position is None:
                missing.append(heading)
            else:
                positions.append((heading, position))
        if missing:
            failures.append((
                "1. 报告骨架",
                f"缺少规定小节：{'、'.join(missing)}；应为 {' → '.join(REPORT_HEADINGS)}",
            ))
        else:
            ordered = [heading for heading, _ in positions]
            if ordered != list(REPORT_HEADINGS):
                failures.append((
                    "1. 报告骨架",
                    f"小节顺序错误：{' → '.join(ordered)}；应为 {' → '.join(REPORT_HEADINGS)}",
                ))

        conclusion_lines = section_lines(
            lines,
            "检索结论",
            find_heading(lines, "证据与来源"),
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
                if not any(label in line for label in CLAIM_TYPES)
            ]
            if missing_types:
                failures.append((
                    "2. 结论类型",
                    f"以下结论未标注事实、来源观点或推断：{missing_types[0][:80]}",
                ))
            missing_verify = [
                line.strip()
                for line in claim_lines
                if not any(label in line for label in VERIFY_LABELS)
            ]
            if missing_verify:
                failures.append((
                    "3. 核验状态",
                    f"以下结论未标注核验状态：{missing_verify[0][:80]}",
                ))

        evidence_pos = find_heading(lines, "证据与来源")
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
            if header_cells and not same_columns(header_cells, EVIDENCE_COLUMNS):
                failures.append((
                    "4. 证据表列名",
                    "表头为「" + " | ".join(header_cells) + "」；应为「"
                    + " | ".join(EVIDENCE_COLUMNS)
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
            if line.strip().startswith(("来源：", "来源:"))
        ]
        verify_lines = [
            line.strip()
            for line in lines
            if line.strip().startswith(("核验：", "核验:"))
        ]

        if not source_lines:
            failures.append((
                "1. 来源",
                "简洁档缺少「来源：」行",
            ))
        else:
            source_text = " ".join(source_lines)
            if "http" not in source_text and "无公开链接" not in source_text:
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
        if line.strip().startswith(("链接状态：", "链接状态:"))
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
