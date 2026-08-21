"""browser-bridge 通道安全校验单测。

覆盖 WS 建连 token 校验(validate_ws_token)与 /transition data_path 白名单
(resolve_inject_path), 对应改进计划 A1 验收项: 无 token/错误 token 被拒绝。
"""

import os
from base64 import b64encode

from astronverse.browser_bridge.security import resolve_inject_path, validate_ws_token


class TestValidateWsToken:
    def test_empty_token_rejected(self):
        assert validate_ws_token(None) is None
        assert validate_ws_token("") is None

    def test_invalid_base64_rejected(self):
        assert validate_ws_token("!!!not-base64!!!") is None
        # 合法 base64 但解码非 utf-8
        assert validate_ws_token(b64encode(b"\xff\xfe\xfd").decode()) is None

    def test_arbitrary_identity_rejected(self):
        # 本机其他进程伪造任意字符串注册 uuid 应被拒绝
        for identity in ["hacker", "admin", "victim-page", "root", "Mozilla"]:
            assert validate_ws_token(b64encode(identity.encode()).decode()) is None, identity

    def test_reserved_uuid_rejected(self):
        # $root$ 是服务端保留标识, 不允许客户端注册
        assert validate_ws_token(b64encode(b"$root$").decode()) is None

    def test_browser_variant_accepted(self):
        for variant in ["$chrome$", "$edge$", "$firefox$", "$360se$", "$360ChromeX$", "$chromium$", "$unknown$"]:
            token = b64encode(variant.encode()).decode()
            assert validate_ws_token(token) == variant, variant

    def test_native_user_agent_accepted(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        assert validate_ws_token(b64encode(ua.encode()).decode()) == ua


class TestResolveInjectPath:
    def _root(self, tmp_path):
        root = tmp_path / "inject"
        root.mkdir()
        return root

    def test_empty_path_rejected(self, tmp_path):
        assert resolve_inject_path("", str(self._root(tmp_path))) is None

    def test_file_under_root_accepted(self, tmp_path):
        root = self._root(tmp_path)
        script = root / "contentInject.js"
        script.write_text("// js")
        assert resolve_inject_path(str(script), str(root)) == str(script)

    def test_dotdot_escape_rejected(self, tmp_path):
        root = self._root(tmp_path)
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")
        escaped = os.path.join(str(root), "..", "secret.txt")
        assert resolve_inject_path(escaped, str(root)) is None

    def test_outside_root_rejected(self, tmp_path):
        root = self._root(tmp_path)
        outside = tmp_path / "outside.js"
        outside.write_text("// js")
        assert resolve_inject_path(str(outside), str(root)) is None

    def test_root_itself_rejected(self, tmp_path):
        root = self._root(tmp_path)
        assert resolve_inject_path(str(root), str(root)) is None

    def test_sibling_dir_prefix_not_bypassed(self, tmp_path):
        # inject_evil 与 inject 共享前缀, 不能被 startswith 误放行
        root = tmp_path / "inject"
        root.mkdir()
        evil = tmp_path / "injectEvil"
        evil.mkdir()
        script = evil / "evil.js"
        script.write_text("// evil")
        assert resolve_inject_path(str(script), str(root)) is None
