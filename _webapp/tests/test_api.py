# -*- coding: utf-8 -*-
"""本地服务端回归测试（纯标准库，不需要 pytest）。

跑法：
    cd _webapp
    python -m unittest discover -s tests -v

测试会自己造一个临时资料根，不会碰真实的课程/书库/密钥文件。
"""
import http.client
import json
import socket
import sys
import tempfile
import threading
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import courses, library   # noqa: E402
import server                     # noqa: E402


FIXTURES = {
    "课程/index.html": "<!DOCTYPE html><html><body>hello 课程</body></html>",
    "课程/a.md": "# 标题\n\ntransformer 测试内容\n",
    "书库/书.md": "# 书\n",
    "docs/说明.md": "# 文档\n",
    "_webapp/.ai-config.json": '{"api_key": "sk-should-never-leak"}',
    ".git/config": "[core]\n",
    "book/.preview/p.md": "# 预览\n",
}

HTML_SIZE = len(FIXTURES["课程/index.html"].encode("utf-8"))


def _read_response(sock):
    """从裸 socket 读一个完整 HTTP 响应（含 chunked 之外的一般情况）。"""
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            return b"", b""
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    while len(rest) < length:
        chunk = sock.recv(65536)
        if not chunk:
            break
        rest += chunk
    return head, rest


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        for rel, text in FIXTURES.items():
            p = cls.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

        cls._orig_root = server.ROOT
        server.ROOT = cls.root
        courses.configure(cls.root, "书库")
        # GBK 编码的中文资料（搜索要走回退解码）
        (cls.root / "课程" / "gbk.md").write_bytes(
            "# GBK 资料\n\n中文检索词 甲乙丙\n".encode("gbk"))
        # 公式页：应被注入 KaTeX；已自带 katex 的页面不应重复注入
        (cls.root / "书库" / "公式.html").write_text(
            "<html><body>文字里提到 KaTeX 也要注入 $x^2$</body></html>", encoding="utf-8")
        (cls.root / "书库" / "已有.html").write_text(
            "<html><head><script src='katex.min.js'></script></head><body>$y$</body></html>",
            encoding="utf-8")

        cls.srv = server.StudyServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        server.ROOT = cls._orig_root
        cls.tmp.cleanup()

    # ---------- helpers ----------
    def req(self, path, method="GET", headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            c.request(method, path, body=body,
                      headers=headers or {"Connection": "close"})
            r = c.getresponse()
            return r.status, dict(r.getheaders()), r.read()
        finally:
            c.close()

    def raw(self):
        return socket.create_connection(("127.0.0.1", self.port), timeout=10)

    # ---------- 路径安全 ----------
    def test_traversal_blocked(self):
        for path in ("/files/../../Windows/win.ini",
                     "/files/..%2F..%2FWindows%2Fwin.ini",
                     "/api/raw?path=..%2F..%2FWindows%2Fwin.ini"):
            st, _, _ = self.req(path)
            self.assertIn(st, (403, 404), "%s 应被拦截，实际 %s" % (path, st))

    def test_sensitive_paths_blocked(self):
        for path in ("/files/_webapp/.ai-config.json",
                     "/files/_webapp/.lan-token",
                     "/files/.git/config",
                     "/api/raw?path=_webapp%2F.ai-config.json",
                     "/api/file?path=_webapp%2F.ai-config.json"):
            st, _, body = self.req(path)
            self.assertEqual(st, 403, "%s 应 403" % path)
            self.assertNotIn(b"sk-", body)

    def test_normal_file_still_served(self):
        st, _, body = self.req("/files/%E8%AF%BE%E7%A8%8B/index.html")
        self.assertEqual(st, 200)
        self.assertEqual(len(body), HTML_SIZE)

    def test_preview_dir_not_blocked(self):
        """.preview 是书库临时预览，不能被黑名单误伤。"""
        st, _, _ = self.req("/files/book/.preview/p.md")
        self.assertEqual(st, 200)

    def test_check_public_rejects_escape(self):
        with self.assertRaises(server.UnsafePath):
            server.check_public("../outside.txt")

    def test_check_public_allows_root(self):
        self.assertEqual(server.check_public(""), server.ROOT)

    # ---------- HEAD ----------
    def test_head_has_no_body(self):
        s = self.raw()
        try:
            s.sendall(b"HEAD /api/ping HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
            head, body = _read_response(s)
        finally:
            s.close()
        self.assertIn(b"200", head.split(b"\r\n")[0])
        self.assertEqual(body, b"")

    # ---------- Range ----------
    def test_range_prefix(self):
        st, h, body = self.req("/api/raw?path=%E8%AF%BE%E7%A8%8B%2Findex.html",
                               headers={"Range": "bytes=0-9", "Connection": "close"})
        self.assertEqual(st, 206)
        self.assertEqual(len(body), 10)
        self.assertTrue(h.get("Content-Range", "").startswith("bytes 0-9/"))

    def test_range_suffix_returns_tail(self):
        full = FIXTURES["课程/index.html"].encode("utf-8")
        st, h, body = self.req("/api/raw?path=%E8%AF%BE%E7%A8%8B%2Findex.html",
                               headers={"Range": "bytes=-10", "Connection": "close"})
        self.assertEqual(st, 206)
        self.assertEqual(body, full[-10:])
        self.assertIn("bytes %d-%d/%d" % (len(full) - 10, len(full) - 1, len(full)),
                      h.get("Content-Range", ""))

    def test_range_out_of_bounds_is_416(self):
        st, h, _ = self.req("/api/raw?path=%E8%AF%BE%E7%A8%8B%2Findex.html",
                            headers={"Range": "bytes=999999-", "Connection": "close"})
        self.assertEqual(st, 416)
        self.assertIn("*/", h.get("Content-Range", ""))

    def test_range_malformed_is_416(self):
        for rng in ("bytes=abc", "bytes=-0", "bytes=5-1"):
            st, _, _ = self.req("/api/raw?path=%E8%AF%BE%E7%A8%8B%2Findex.html",
                                headers={"Range": rng, "Connection": "close"})
            self.assertEqual(st, 416, "Range: %s" % rng)

    # ---------- POST body ----------
    def test_oversized_body_does_not_desync(self):
        """超限 body 必须把剩余字节读掉，否则同一连接上的下一个请求会错位。"""
        payload = b'{"x":"' + b"A" * 300000 + b'"}'
        s = self.raw()
        try:
            s.sendall(b"POST /api/ai/config HTTP/1.1\r\nHost: x\r\n"
                      b"Content-Type: application/json\r\n"
                      b"Content-Length: %d\r\n\r\n" % len(payload) + payload)
            head1, _ = _read_response(s)
            self.assertIn(b"400", head1.split(b"\r\n")[0])

            s.sendall(b"GET /api/ping HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
            head2, body2 = _read_response(s)
            self.assertIn(b"200", head2.split(b"\r\n")[0])
            self.assertIn(b'"ok"', body2)
        finally:
            s.close()

    # ---------- 路由 ----------
    def test_library_info_when_disabled(self):
        st, _, body = self.req("/api/library/info")
        self.assertEqual(st, 200)
        self.assertFalse(json.loads(body)["enabled"])

    def test_unknown_path_404(self):
        st, _, _ = self.req("/no/such/route")
        self.assertEqual(st, 404)

    def test_search_finds_content(self):
        server._search_cache["ts"] = 0
        st, _, body = self.req("/api/search?q=transformer")
        self.assertEqual(st, 200)
        data = json.loads(body)
        self.assertGreaterEqual(data["count"], 1)

    def test_search_handles_gbk_files(self):
        """GBK 编码的中文资料也要搜得到（旧实现按 UTF-8 读会整篇变空）。"""
        server._search_cache["ts"] = 0
        st, _, body = self.req("/api/search?q=" + urllib.parse.quote("甲乙丙"))
        self.assertEqual(st, 200)
        data = json.loads(body)
        self.assertGreaterEqual(data["count"], 1, "GBK 文件没有被索引/命中")

    def test_math_injection(self):
        """正文里出现 KaTeX 一词不应阻止注入；已引入 katex 的页面不应重复注入。"""
        st, _, body = self.req("/mathfiles/%E4%B9%A6%E5%BA%93/%E5%85%AC%E5%BC%8F.html")
        self.assertEqual(st, 200)
        self.assertIn(b"katex.min.js", body)
        st, _, body = self.req("/mathfiles/%E4%B9%A6%E5%BA%93/%E5%B7%B2%E6%9C%89.html")
        self.assertEqual(st, 200)
        self.assertEqual(body.count(b"katex.min.js"), 1, "不该重复注入")

    def test_tree_lists_dirs(self):
        st, _, body = self.req("/api/tree")
        self.assertEqual(st, 200)
        names = [d["name"] for d in json.loads(body)["dirs"]]
        self.assertIn("课程", names)
        # _webapp 属于 SKIP_DIRS，树里不该出现
        self.assertNotIn("_webapp", names)

    # ---------- 纯函数 ----------
    def test_classify_kinds(self):
        self.assertEqual(server.classify("a.md", 100)[0], "markdown")
        self.assertEqual(server.classify("a.ipynb", 100)[0], "notebook")
        self.assertEqual(server.classify("a.mp4", 100)[0], "binary")
        self.assertEqual(server.get_ext(".gitignore"), ".gitignore")

    def test_log_message_only_errors(self):
        """只记 4xx / 5xx：200 静默，404 / 500 各输出一行。"""
        import io
        import types

        class Dummy:
            def log_date_time_string(self):
                return "T"

        dummy = Dummy()
        dummy.log_message = types.MethodType(server.Handler.log_message, dummy)

        def cap(*a):
            buf = io.StringIO()
            old, sys.stderr = sys.stderr, buf
            try:
                dummy.log_message(*a)
            finally:
                sys.stderr = old
            return buf.getvalue()

        self.assertEqual(cap('"%s" %s %s', '"GET / HTTP/1.1"', "200", "10"), "")
        self.assertIn("404", cap('"%s" %s %s', '"GET /x HTTP/1.1"', "404", "-"))
        self.assertIn("500", cap('"%s" %s %s', '"POST /y HTTP/1.1"', "500", "-"))

    def test_find_port_skips_used(self):
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        used = blocker.getsockname()[1]
        try:
            picked = server.find_port(used, 1)
            # 端口被占时不能返回同一个端口（Windows 下 SO_REUSEADDR 曾经能做到）
            self.assertNotEqual(picked, used)
        except RuntimeError:
            pass   # 找不到也算正确行为
        finally:
            blocker.close()


class LlmCallTest(unittest.TestCase):
    """用本地假接口验证 ai.llm_call 的请求体与解析（不发真实请求、不花钱）。"""

    @classmethod
    def setUpClass(cls):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Stub(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                cls.last_body = json.loads(raw.decode("utf-8"))
                cls.last_auth = self.headers.get("Authorization")
                if cls.last_body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    for text in ("你", "好"):
                        payload = ("data: " + json.dumps(
                            {"choices": [{"delta": {"content": text}}]},
                            ensure_ascii=False) + "\n\n").encode("utf-8")
                        self.wfile.write(b"%x\r\n" % len(payload) + payload + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                else:
                    body = json.dumps(
                        {"choices": [{"message": {"content": "pong"}}]},
                        ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

        cls.stub = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        cls.port = cls.stub.server_address[1]
        threading.Thread(target=cls.stub.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.stub.shutdown()
        cls.stub.server_close()

    def cfg(self):
        return {"base_url": "http://127.0.0.1:%d/v1" % self.port,
                "model": "stub-model", "api_key": "sk-test",
                "temperature": 0.3, "max_tokens": 32}

    def test_non_stream_call(self):
        from app import ai
        out = ai.llm_call(self.cfg(), [{"role": "user", "content": "hi"}])
        self.assertEqual(out, "pong")
        self.assertEqual(self.last_auth, "Bearer sk-test")
        body = self.last_body
        self.assertEqual(body["model"], "stub-model")
        self.assertFalse(body["stream"])
        self.assertEqual(body["messages"][0]["content"], "hi")

    def test_stream_call(self):
        from app import ai
        resp = ai.llm_call(self.cfg(), [{"role": "user", "content": "hi"}], stream=True)
        try:
            chunks = []
            for line in resp:
                line = line.decode("utf-8").strip()
                if line.startswith("data:"):
                    obj = json.loads(line[5:].strip())
                    chunks.append(obj["choices"][0]["delta"]["content"])
        finally:
            resp.close()
        self.assertEqual("".join(chunks), "你好")


if __name__ == "__main__":
    unittest.main(verbosity=2)
