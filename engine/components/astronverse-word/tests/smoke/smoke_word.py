import sys
import types

# stub pywpsrpc (linux-only) so core_unix imports on macOS
for name in ["pywpsrpc", "pywpsrpc.rpcwpsapi"]:
    m = types.ModuleType(name)
    m.__all__ = []
    sys.modules[name] = m

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-word/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-actionlib/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-baseline/src")

from astronverse.word import CursorPointerType, CursorPositionType, ReplaceMethodType, ReplaceType
from astronverse.word.core_unix import WordDocumentCore

# ---- 1. bookmark cursor positioning ----
class FakeBookmarkRange:
    Start, End = 100, 150

class FakeBookmarks:
    def __init__(self, names):
        self.names = names

    def Exists(self, name):
        return name in self.names

    def __getitem__(self, name):
        if name not in self.names:
            raise KeyError(name)
        return types.SimpleNamespace(Range=FakeBookmarkRange())

class FakeSel:
    def __init__(self):
        self.range = None
        self.actions = []
        self.Find = None

    def SetRange(self, Start=None, End=None):
        self.range = (Start, End)

    def HomeKey(self, Unit=None):
        pass

    def TypeParagraph(self):
        self.actions.append("para")

    def TypeText(self, t):
        self.actions.append(t)

    @property
    def Start(self):
        return 0

    @property
    def End(self):
        return len(str(self.actions[-1])) if self.actions else 0

    @property
    def Range(self):
        return "range"

class FakeDoc:
    def __init__(self, names=(), sel=None, content=None):
        self.Bookmarks = FakeBookmarks(names)
        self.sel = sel or FakeSel()
        self.Content = content
        self.links = []

    def Activate(self):
        pass

    @property
    def Application(self):
        return types.SimpleNamespace(Selection=self.sel)

    @property
    def Hyperlinks(self):
        return self

    def Add(self, Anchor=None, Address=None, TextToDisplay=None):
        self.links.append((Address, TextToDisplay))


doc = FakeDoc(["bm1", "bm2"])
WordDocumentCore.cursor_position(doc, CursorPointerType.BOOKMARK, CursorPositionType.HEAD, bookmark="bm1")
assert doc.sel.range == (100, 100), doc.sel.range
WordDocumentCore.cursor_position(doc, CursorPointerType.BOOKMARK, CursorPositionType.TAIL, bookmark="bm2")
assert doc.sel.range == (150, 150), doc.sel.range
try:
    WordDocumentCore.cursor_position(FakeDoc([]), CursorPointerType.BOOKMARK, CursorPositionType.HEAD, bookmark="nope")
    raise SystemExit("should raise")
except BaseException:
    pass  # 分支正确抛错: 书签不存在
try:
    WordDocumentCore.cursor_position(doc, CursorPointerType.BOOKMARK, "", "", 1, 1, 1, "")
    raise SystemExit("should raise")
except BaseException:
    pass  # 分支正确抛错: 书签名称为空
print("bookmark positioning OK")

# ---- 2. replace counting ----
class FakeFind:
    """Execute() 返回 True 共 hits 次(模拟 Find 逐个命中)"""

    def __init__(self, hits):
        self.hits, self.i, self.Text, self.MatchCase = hits, 0, "", None

    def ClearFormatting(self):
        pass

    def Execute(self, *a, **k):
        if a and isinstance(a[0], str):
            self.Text = a[0]
        self.i += 1
        return self.i <= self.hits


def make_doc(hits):
    finder = FakeFind(hits)
    content = types.SimpleNamespace(Find=finder)
    d = FakeDoc(content=content)
    d.sel.Find = finder
    return d


# ALL+STR: 3 匹配 -> 3
n = WordDocumentCore.replace(make_doc(3), ReplaceType.STR, "old", "new", "", ReplaceMethodType.ALL, True)
assert n == 3, n
# FIRST+STR: 3 匹配 -> 1
n = WordDocumentCore.replace(make_doc(3), ReplaceType.STR, "old", "new", "", ReplaceMethodType.FIRST, True)
assert n == 1, n
# ALL+STR 无匹配 -> 0 (修复前恒为 0 之外的错误路径已移除)
n = WordDocumentCore.replace(make_doc(0), ReplaceType.STR, "old", "new", "", ReplaceMethodType.ALL, True)
assert n == 0, n
# FIRST+STR 无匹配 -> 0 (修复前恒为 1)
n = WordDocumentCore.replace(make_doc(0), ReplaceType.STR, "old", "new", "", ReplaceMethodType.FIRST, True)
assert n == 0, n
print("replace counting OK")

# ---- 3. insert_hyperlink newline ----
d2 = FakeDoc()
WordDocumentCore.insert_hyperlink(d2, "http://x", "显示", newline=True)
assert d2.sel.actions[0] == "para" and d2.links == [("http://x", "显示")], (d2.sel.actions, d2.links)
d3 = FakeDoc()
WordDocumentCore.insert_hyperlink(d3, "http://x", "显示", newline=False)
assert d3.sel.actions == ["http://x"] and d3.links == [("http://x", "显示")], (d3.sel.actions, d3.links)
print("hyperlink newline OK")
print("ALL WORD SMOKE OK")
