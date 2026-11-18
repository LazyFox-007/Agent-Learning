# -*- coding: utf-8 -*-
"""练习区（保存 + 运行）的回归测试。

跑法：python -m unittest discover -s tests -v
测试用临时资料根和临时配置文件，不会碰真实的 练习区/ 和 .ide-config.json。
"""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ide   # noqa: E402
import server         # noqa: E402


class IdeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)

        cls._orig_root = server.ROOT
        cls._orig_cfg = ide.CONFIG_FILE
        cls._orig_enabled = ide.ENABLED

        server.ROOT = cls.root
        ide.configure(cls.root)
        ide.CONFIG_FILE = cls.root / ".ide-config.json"
        ide.ENABLED = True

        cls.srv = server.StudyServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        server.ROOT = cls._orig_root
        ide.CONFIG_FILE = cls._orig_cfg
        ide.ENABLED = cls._orig_enabled
        cls.tmp.cleanup()

    # ---------- helpers ----------
    def setUp(self):
        # 每个用例都从默认配置开始，避免用例之间互相污染
        ide.save_config(dict(ide.DEFAULT))

    def call(self, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            if body is None:
                c.request("GET", path, headers={"Connection": "close"})
            else:
                c.request("POST", path, body=json.dumps(body),
                          headers={"Content-Type": "application/json",
                                   "Connection": "close"})
            r = c.getresponse()
            data = r.read()
            return r.status, (json.loads(data) if data else {})
        finally:
            c.close()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    # ---------- 状态 ----------
    def test_status(self):
        st, d = self.call("/api/ide/status")
        self.assertEqual(st, 200)
        self.assertTrue(d["enabled"])
        self.assertEqual(d["workspace"], "练习区")
        self.assertTrue(d["python"])

    def test_list_workspace(self):
        self.write("练习区/aa.py", "print(1)\n")
        self.write("练习区/sub/bb.py", "print(2)\n")
        st, d = self.call("/api/ide/list")
        self.assertEqual(st, 200)
        self.assertEqual(d["workspace"], "练习区")
        names = [i["path"] for i in d["items"]]
        self.assertIn("练习区/aa.py", names)
        self.assertIn("练习区/sub/bb.py", names)

    # ---------- 保存 ----------
    def test_save_into_workspace(self):
        st, d = self.call("/api/ide/save",
                          {"path": "练习区/hello.py", "content": "print('hi')\n"})
        self.assertEqual(st, 200, d)
        self.assertEqual(d["path"], "练习区/hello.py")
        self.assertEqual((self.root / "练习区" / "hello.py").read_text(encoding="utf-8"),
                         "print('hi')\n")

    def test_save_creates_subdirs(self):
        st, d = self.call("/api/ide/save",
                          {"path": "练习区/ch01/a/b.py", "content": "x = 1\n"})
        self.assertEqual(st, 200, d)
        self.assertTrue((self.root / "练习区" / "ch01" / "a" / "b.py").is_file())

    def test_save_outside_workspace_rejected(self):
        """课程目录是只读的，只能写工作区。"""
        st, d = self.call("/api/ide/save", {"path": "课程/evil.py", "content": "x"})
        self.assertEqual(st, 400, d)
        self.assertFalse((self.root / "课程" / "evil.py").exists())

    def test_save_rejects_traversal(self):
        for bad in ("../escape.py", "..\\escape.py", "/abs.py", "C:/x.py", "a/../../b.py"):
            st, d = self.call("/api/ide/save", {"path": bad, "content": "x"})
            self.assertEqual(st, 400, "%s 应被拒绝，实际 %s %s" % (bad, st, d))

    def test_save_rejects_oversize(self):
        st, d = self.call("/api/ide/save",
                          {"path": "练习区/big.py", "content": "x" * (3 * 1024 * 1024)})
        self.assertEqual(st, 400)

    # ---------- 运行 ----------
    def test_run_ok(self):
        self.write("练习区/ok.py", "print('hello')\n")
        st, d = self.call("/api/ide/run", {"path": "练习区/ok.py"})
        self.assertEqual(st, 200, d)
        self.assertTrue(d["ok"])
        self.assertEqual(d["code"], 0)
        self.assertIn("hello", d["stdout"])
        self.assertFalse(d["timedOut"])

    def test_run_error_output(self):
        self.write("练习区/err.py", "raise SystemExit(3)\n")
        st, d = self.call("/api/ide/run", {"path": "练习区/err.py"})
        self.assertEqual(st, 200)
        self.assertEqual(d["code"], 3)

    def test_run_rejects_non_python(self):
        self.write("练习区/a.txt", "hi")
        st, d = self.call("/api/ide/run", {"path": "练习区/a.txt"})
        self.assertEqual(st, 400)

    def test_run_rejects_outside_root(self):
        st, d = self.call("/api/ide/run", {"path": "../outside.py"})
        self.assertEqual(st, 400)

    def test_run_timeout_kills(self):
        self.write("练习区/slow.py", "import time\ntime.sleep(30)\n")
        # 先把超时调到 1 秒
        self.call("/api/ide/config", {"timeout": 1})
        try:
            st, d = self.call("/api/ide/run", {"path": "练习区/slow.py"})
            self.assertEqual(st, 200, d)
            self.assertTrue(d["timedOut"], "应该因超时被杀")
            self.assertLess(d["ms"], 15000)
        finally:
            self.call("/api/ide/config", {"timeout": 10})

    # ---------- 配置 ----------
    def test_config_roundtrip(self):
        st, d = self.call("/api/ide/config",
                          {"workspace": "mywork", "python": "", "timeout": 7})
        self.assertEqual(st, 200, d)
        self.assertEqual(d["workspace"], "mywork")
        self.assertEqual(d["timeout"], 7)
        self.assertTrue((self.root / "mywork").is_dir())
        # 存到文件里了
        saved = json.loads(ide.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual(saved["workspace"], "mywork")
        self.call("/api/ide/config", {"workspace": "练习区", "timeout": 10})

    def test_config_rejects_escape_workspace(self):
        st, d = self.call("/api/ide/config", {"workspace": "../outside"})
        self.assertEqual(st, 400)


class IdeDisabledTest(unittest.TestCase):
    def test_save_forbidden_when_disabled(self):
        old = ide.ENABLED
        ide.ENABLED = False
        try:
            tmp = tempfile.TemporaryDirectory()
            root = Path(tmp.name)
            orig = server.ROOT
            server.ROOT = root
            ide.configure(root)
            srv = server.StudyServer(("127.0.0.1", 0), server.Handler)
            port = srv.server_address[1]
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                c.request("POST", "/api/ide/save",
                          body=json.dumps({"path": "a.py", "content": "x"}),
                          headers={"Content-Type": "application/json",
                                   "Connection": "close"})
                r = c.getresponse()
                self.assertEqual(r.status, 403)
                r.read()
                c.close()
            finally:
                srv.shutdown()
                srv.server_close()
                server.ROOT = orig
                tmp.cleanup()
        finally:
            ide.ENABLED = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
