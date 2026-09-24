#!/usr/bin/env python3
"""来源链接批量校验（verifiable-research 可选本地增强）。

用法:
  python check_sources.py <包含URL的文本文件>
  cat 来源表.md | python check_sources.py
  python check_sources.py <文件> --probe     # 附加联网探活，默认关闭

输入为报告档的证据与来源表等任意含 URL 的文本。
检查项:
  1. URL 语法（协议、域名、全角标点）
  2. 精确重复提示
  3. 规范化重复提示（剔除 utm_* / spm / from 等追踪参数与尾部斜杠后比对）
  4. 疑似链接行（行内含 http 却解析不出有效 URL，需人工检查）
退出码: 0=全部通过; 1=发现问题; 2=输入中未发现 URL。
默认不发起网络请求; --probe 仅发送只读 HEAD/GET 用于探活，超时 5 秒。
--probe 仅允许 80/443 端口；解析后固定已校验的公网 IP，禁止 localhost、私网、
链路本地、保留地址和云元数据地址，并对每次重定向重新解析和校验。
本脚本不写入、不修改任何文件。

--probe 且无问题时，输出末尾先打印「链接探活」摘要行（仅审计模式展示，不进入普通正文），
再附「异常链接区块」：其中异常链接清单可直接照抄进报告正文，不必自行计算。区块中的
「第 N 条链接」为该链接在唯一 URL 中的序号（重复引用只探活一次，不视为错误）。
区块前的「落位要求」说明异常清单贴到报告的哪个位置、以及不得改写形态；
摘要行位于区块之外，避免整体照抄时把审计信息带进正文。
存在问题时（退出码 1）不输出该区块，需先修复问题并重跑。
"""
from __future__ import annotations

import argparse
import errno
import http.client
import ipaddress
import re
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>\"'`|，。；：「」『』（）]+", re.IGNORECASE)
FULLWIDTH_RE = re.compile(r"[，。；：「」『』（）￥]")
TRAILING_PUNCTUATION = ".,;:!?"
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "spm", "from", "share_token", "share_medium",
}
SENSITIVE_QUERY_PARAMS = {
    "access_token", "api_key", "apikey", "auth", "authorization",
    "client_secret", "key", "password", "passwd", "secret", "share_token",
    "sig", "signature", "token",
}
ALLOWED_PORTS = {80, 443}


def clean_url(url: str) -> str:
    url = url.rstrip(TRAILING_PUNCTUATION)
    pairs = {")": "(", "]": "[", "}": "{"}
    while url and url[-1] in pairs:
        opener = pairs[url[-1]]
        if url.count(url[-1]) <= url.count(opener):
            break
        url = url[:-1].rstrip(TRAILING_PUNCTUATION)
    return url


def normalize(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def redact_url(url: str) -> str:
    """隐藏 URL 用户信息和常见敏感查询参数，避免把密钥写入日志。"""
    try:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
    except ValueError:
        return "<无法解析的 URL>"
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = f"{hostname}:{port}" if port is not None else hostname

    query = [
        (key, "[REDACTED]" if key.lower() in SENSITIVE_QUERY_PARAMS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    encoded_query = urlencode(query).replace("%5BREDACTED%5D", "[REDACTED]")
    fragment = "[REDACTED]" if parts.fragment else ""
    return urlunsplit(
        (parts.scheme.lower(), netloc, parts.path, encoded_query, fragment)
    )


def syntax_problems(url: str) -> list:
    problems = []
    if FULLWIDTH_RE.search(url):
        problems.append("URL 含全角标点")
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        parts.port
    except ValueError as exc:
        return problems + [f"URL 结构无效：{exc}"]
    if parts.scheme.lower() not in ("http", "https"):
        problems.append("非 http/https 协议")
    if not parts.netloc or not hostname:
        problems.append("缺少域名")
    elif "." not in hostname and hostname != "localhost" and ":" not in hostname:
        problems.append("域名异常（缺少点号）")
    if parts.username is not None or parts.password is not None:
        problems.append("URL 禁止携带用户名或密码")
    return problems


def probe_verdict(status: int) -> str:
    if status in (200, 201, 202, 204, 206, 301, 302, 303, 307, 308):
        return "在线"
    if status in (404, 410):
        return "链接已失效"
    if status in (401, 403, 405, 429):
        return "反爬或限流，无法确认在线状态"
    if 500 <= status < 600:
        return "服务端错误，暂时无法确认在线状态"
    return "访问异常，无法确认在线状态"


def probe_online(result: str) -> bool:
    return result.endswith("| 在线")


def resolve_public_target(url: str) -> tuple[str, int]:
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError("只允许探活 http/https 地址")
    hostname = parts.hostname
    if not hostname:
        raise ValueError("URL 缺少域名")
    if parts.username is not None or parts.password is not None:
        raise ValueError("禁止 URL 携带用户名或密码")
    if hostname.lower() == "localhost":
        raise ValueError("禁止访问 localhost")

    try:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise ValueError(f"URL 端口无效: {exc}") from exc
    if port not in ALLOWED_PORTS:
        raise ValueError("探活仅允许 80/443 端口")
    try:
        addresses = sorted({
            item[4][0].split("%", 1)[0]
            for item in socket.getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        })
    except OSError as exc:
        raise ValueError(f"无法解析域名: {exc}") from exc
    if not addresses:
        raise ValueError("域名未解析到可用 IP 地址")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise ValueError(f"返回了无效 IP 地址: {address}") from None
        if not ip.is_global:
            raise ValueError(f"禁止访问非公网地址: {address}")
    return addresses[0], port


def network_safety_problem(url: str) -> str | None:
    try:
        resolve_public_target(url)
    except ValueError as exc:
        return str(exc)
    return None


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, *args, target_ip: str, **kwargs):
        super().__init__(host, *args, **kwargs)
        self._target_ip = target_ip

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._target_ip, self.port),
            self.timeout,
            self.source_address,
        )
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as exc:
            if exc.errno != errno.ENOPROTOOPT:
                raise
        if self._tunnel_host:
            self._tunnel()


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *args, target_ip: str, **kwargs):
        super().__init__(host, *args, **kwargs)
        self._target_ip = target_ip

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._target_ip, self.port),
            self.timeout,
            self.source_address,
        )
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as exc:
            if exc.errno != errno.ENOPROTOOPT:
                raise
        if self._tunnel_host:
            self._tunnel()
            server_hostname = self._tunnel_host
        else:
            server_hostname = self.host
        self.sock = self._context.wrap_socket(
            self.sock,
            server_hostname=server_hostname,
        )


def _pinned_http_factory(target_ip: str):
    def factory(host: str, timeout=None, **kwargs):
        return PinnedHTTPConnection(
            host,
            timeout=timeout,
            target_ip=target_ip,
            **kwargs,
        )

    return factory


def _pinned_https_factory(target_ip: str):
    def factory(host: str, timeout=None, **kwargs):
        return PinnedHTTPSConnection(
            host,
            timeout=timeout,
            target_ip=target_ip,
            **kwargs,
        )

    return factory


class PinnedHTTPHandler(urllib_request.HTTPHandler):
    def http_open(self, req):
        try:
            target_ip, _ = resolve_public_target(req.full_url)
        except ValueError as exc:
            raise urllib_error.URLError(str(exc)) from exc
        return self.do_open(_pinned_http_factory(target_ip), req)


class PinnedHTTPSHandler(urllib_request.HTTPSHandler):
    def https_open(self, req):
        try:
            target_ip, _ = resolve_public_target(req.full_url)
        except ValueError as exc:
            raise urllib_error.URLError(str(exc)) from exc
        return self.do_open(_pinned_https_factory(target_ip), req)


def _open_request(request, timeout: float):
    class SafeRedirectHandler(urllib_request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            target = urljoin(req.full_url, newurl)
            try:
                resolve_public_target(target)
            except ValueError as exc:
                raise urllib_error.URLError(
                    f"重定向被安全策略阻止: {exc}"
                ) from exc
            return super().redirect_request(req, fp, code, msg, headers, target)

    opener = urllib_request.build_opener(
        urllib_request.ProxyHandler({}),
        SafeRedirectHandler,
        PinnedHTTPHandler,
        PinnedHTTPSHandler,
    )
    return opener.open(request, timeout=timeout)


def probe(url: str, timeout: float = 5.0) -> str:
    safety_problem = network_safety_problem(url)
    if safety_problem:
        return f"安全限制 | {safety_problem}"

    headers = {"User-Agent": "Mozilla/5.0 (verifiable-research link checker)"}
    for method in ("HEAD", "GET"):
        try:
            request = urllib_request.Request(url, method=method, headers=headers)
            with _open_request(request, timeout) as response:
                return f"HTTP {response.status} | {probe_verdict(response.status)}"
        except urllib_error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue
            return f"HTTP {exc.code} | {probe_verdict(exc.code)}"
        except Exception as exc:
            names = {type(exc).__name__}
            reason = getattr(exc, "reason", None)
            if reason is not None:
                names.add(type(reason).__name__)
            if any("Timeout" in name for name in names):
                return "超时 | 无法确认在线状态"
            return f"访问失败({'/'.join(sorted(names))}) | 无法确认在线状态"
    return "重试后仍无法确认在线状态"


def print_paste_block(results: list) -> None:
    online = sum(1 for _, _, result in results if probe_online(result))
    print(f"链接探活：{online}/{len(results)} 在线（审计信息，仅审计模式展示，不进入普通正文）")
    print()
    print("【落位要求】存在异常链接时，把下面两条横线之间的「异常链接」部分原样放入报告档「证据与来源」表格正下方（紧接表格、位于「来源分歧」之前）；简单档置于来源行之后。顶格书写，不得加项目符号、加粗或缩进，不得改写结论措辞；无异常时正文写「异常链接：无」。上面的「链接探活」摘要行仅审计模式展示，不进入普通正文。")
    print("--- 异常链接区块开始（仅含异常链接部分，照抄，勿改写）---")
    anomalies = [
        (index, redact_url(url), result)
        for index, url, result in results
        if not probe_online(result)
    ]
    if anomalies:
        print("异常链接：")
        for index, url, result in anomalies:
            print(f"- 第 {index} 条链接 | {url} | {result}")
    else:
        print("异常链接：无")
    print("--- 异常链接区块结束 ---")


def main() -> int:
    parser = argparse.ArgumentParser(description="来源链接批量校验")
    parser.add_argument("input_file", nargs="?", help="包含 URL 的文本文件；缺省读取 stdin")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="附加联网探活；仅在用户明确同意后使用（需要网络）",
    )
    args = parser.parse_args()

    if args.input_file:
        try:
            with open(args.input_file, encoding="utf-8-sig") as handle:
                text = handle.read()
        except OSError as exc:
            print(f"无法读取输入文件: {exc}")
            return 2
    else:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        text = sys.stdin.read()

    entries = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in URL_RE.finditer(line):
            url = clean_url(match.group(0))
            if url:
                entries.append((line_no, url))

    extracted_lines = {line_no for line_no, _ in entries}
    scheme_pattern = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://")
    broken_link_lines = [
        line_no
        for line_no, line in enumerate(text.splitlines(), start=1)
        if ("http" in line.lower() or scheme_pattern.search(line)) and line_no not in extracted_lines
    ]

    if not entries:
        if broken_link_lines:
            print("发现疑似链接但无法解析出有效 URL（可能含全角标点或协议错误），需人工检查:")
            for line_no in broken_link_lines:
                print(f"  行 {line_no}")
            print("\n校验完成: 发现无法解析的疑似链接。")
            return 1
        print("输入中未发现任何 URL，无可校验内容。")
        return 2

    problems = 0
    duplicates = 0
    seen_exact = {}
    seen_normalized = {}
    unique_for_probe = []
    print(f"共发现 {len(entries)} 条 URL。")
    for index, (line_no, url) in enumerate(entries, start=1):
        issues = syntax_problems(url)
        if issues:
            problems += 1
            print(
                f"[{index:03d}] 行 {line_no} | 问题: {'; '.join(issues)}"
                f" | {redact_url(url)}"
            )
            continue

        normalized = normalize(url)
        duplicate_of = None
        duplicate_kind = ""
        if url in seen_exact:
            duplicate_of = seen_exact[url]
            duplicate_kind = "完全重复"
        elif normalized in seen_normalized:
            duplicate_of = seen_normalized[normalized]
            duplicate_kind = "仅差追踪参数"
        else:
            seen_exact[url] = index
            seen_normalized[normalized] = index
            unique_for_probe.append((len(unique_for_probe) + 1, index, line_no, url))

        if duplicate_of is not None:
            duplicates += 1
            print(
                f"[{index:03d}] 行 {line_no} | 提示: 与第 {duplicate_of} 条"
                f"{duplicate_kind}，探活复用首次出现项 | {redact_url(url)}"
            )
        else:
            print(f"[{index:03d}] 行 {line_no} | 通过 | {redact_url(url)}")

    if broken_link_lines:
        problems += len(broken_link_lines)
        print("\n以下各行疑似包含链接，但无法解析出有效 URL（可能含全角标点或协议错误），需人工检查:")
        for line_no in broken_link_lines:
            print(f"  行 {line_no}")

    probe_results = []
    if args.probe and unique_for_probe:
        print(f"\n探活 {len(unique_for_probe)} 个唯一 URL（8 并发，单个超时 5 秒）:")
        # pool.map 按输入顺序返回结果，保证逐条输出与异常链接区块的顺序稳定可复现
        with ThreadPoolExecutor(max_workers=8) as pool:
            verdicts = list(pool.map(probe, [url for _, _, _, url in unique_for_probe]))
        for (probe_index, original_index, line_no, url), verdict in zip(unique_for_probe, verdicts):
            probe_results.append((probe_index, url, verdict))
            print(
                f"  [{probe_index}] {verdict} | 行 {line_no}，"
                f"原 URL 序号 {original_index} | {redact_url(url)}"
            )

    if problems:
        print(f"\n校验完成: 发现 {problems} 条问题 URL。")
        if args.probe:
            print("存在问题 URL，本次不输出异常链接区块；请先修复上述问题并重跑。")
        return 1
    duplicate_note = f"，另有 {duplicates} 条重复提示" if duplicates else ""
    if probe_results:
        anomaly_count = sum(
            1 for _, _, result in probe_results if not probe_online(result)
        )
        print(
            f"\n校验完成: URL 语法全部 {len(entries)} 条通过{duplicate_note}"
            f"；探活异常 {anomaly_count}/{len(probe_results)}。"
        )
        print_paste_block(probe_results)
    else:
        print(f"\n校验完成: 全部 {len(entries)} 条通过{duplicate_note}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
