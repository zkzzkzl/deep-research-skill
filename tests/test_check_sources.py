from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_sources as subject


class SafetyTests(unittest.TestCase):
    def test_rejects_localhost_and_private_addresses(self):
        for url in (
            "http://localhost/",
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/",
        ):
            with self.subTest(url=url):
                self.assertIsNotNone(subject.network_safety_problem(url))

    def test_rejects_nonstandard_port(self):
        self.assertEqual(
            subject.network_safety_problem("https://example.com:8443/"),
            "探活仅允许 80/443 端口",
        )

    @patch("check_sources.socket.getaddrinfo")
    def test_pins_validated_public_ip(self, getaddrinfo):
        getaddrinfo.return_value = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 443),
            )
        ]
        self.assertEqual(
            subject.resolve_public_target("https://example.com/"),
            ("93.184.216.34", 443),
        )

    @patch("check_sources.socket.getaddrinfo")
    def test_rejects_dns_answer_with_private_address(self, getaddrinfo):
        getaddrinfo.return_value = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.2", 443),
            )
        ]
        with self.assertRaisesRegex(ValueError, "禁止访问非公网地址"):
            subject.resolve_public_target("https://example.com/")

    def test_redacts_userinfo_sensitive_query_and_fragment(self):
        self.assertEqual(
            subject.redact_url(
                "https://user:password@example.com/path"
                "?access_token=secret&view=full#private"
            ),
            "https://example.com/path"
            "?access_token=[REDACTED]&view=full#[REDACTED]",
        )

    def test_syntax_rejects_userinfo(self):
        self.assertIn(
            "URL 禁止携带用户名或密码",
            subject.syntax_problems("https://user:password@example.com/"),
        )


if __name__ == "__main__":
    unittest.main()
