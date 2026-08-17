import json

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.browser import *
from astronverse.browser.browser import Browser
from astronverse.browser.browser_element import get_default_browser
from astronverse.browser.browser_script import eval_js_code
from astronverse.browser.error import *


def _xpath_param(key: str = "xpath", required: bool = True):
    return atomicMg.param(
        key,
        types="Str",
        formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
        required=required,
    )


def _frame_param():
    return atomicMg.param("frame", required=False)


class BrowserIframe:
    """浏览器 IFrame 跨域操作类，提供跨域 iframe 内元素的操作方法。

    通过 runJS 通道携带 isFrame/iframeXpath 路由到目标 frame 执行，
    跨域 iframe 由插件 CDP frame 上下文（frameContextIdMap）分发。
    """

    @staticmethod
    def _get_default_browser_or_raise(browser_obj):
        if not browser_obj:
            browser_obj = get_default_browser()
        if not browser_obj:
            raise BaseException(WEB_GET_BROWSER_ERROR, "未找到可用浏览器，请先打开或获取浏览器对象")
        return browser_obj

    @staticmethod
    def _resolve_frame(browser_obj: Browser, frame: dict):
        """解析生效 frame：显式传入优先，否则回退 browser_obj.frame；返回 None 表示主文档"""
        effective = frame if frame else (browser_obj.frame if hasattr(browser_obj, "frame") else None)
        if effective is None:
            return None
        if not isinstance(effective, dict) or not effective.get("iframeXpath"):
            raise BaseException(
                PARAMETER_INVALID_FORMAT.format(str(effective)), "无效的 iframe 对象，请使用 初始化iframe 获取"
            )
        return effective

    @staticmethod
    def _run_js_in_frame(browser_obj: Browser, js_code: str, frame: dict, time_out: float = 30):
        """runJS 通道执行 JS：frame 为 None 时主文档执行，否则按 iframeXpath 路由到目标 frame"""
        data = {"code": js_code}
        if frame is not None:
            data["isFrame"] = True
            data["iframeXpath"] = frame["iframeXpath"]
        return browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="runJS",
            data=data,
            timeout=float(time_out),
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param("locate_mode"),
            atomicMg.param("index", types="Int", required=False),
            atomicMg.param("name", types="Str", required=False),
            atomicMg.param(
                "xpath",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
            atomicMg.param("parent_frame", required=False),
        ],
        outputList=[atomicMg.param("frame", types="Dict")],
    )
    def init_iframe(
        browser_obj: Browser = None,
        locate_mode: FrameLocateType = FrameLocateType.Index,
        index: int = 0,
        name: str = "",
        xpath: str = "",
        parent_frame: dict = None,
    ):
        """初始化iframe(定位页面中的iframe并生成frame标识)。"""
        if locate_mode == FrameLocateType.Index and index is None:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(str(index)), "iframe 序号不能为空")
        if locate_mode == FrameLocateType.Name and not name:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(name), "iframe 名称不能为空")
        if locate_mode == FrameLocateType.Xpath and not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(xpath), "iframe XPath 不能为空")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        parent_frame = BrowserIframe._resolve_frame(browser_obj, parent_frame)

        if locate_mode == FrameLocateType.Index:
            mode_js, val_js = "index", json.dumps(int(index))
        elif locate_mode == FrameLocateType.Name:
            mode_js, val_js = "name", json.dumps(str(name), ensure_ascii=False)
        else:
            mode_js, val_js = "xpath", json.dumps(str(xpath), ensure_ascii=False)

        js_code = (
            "function main(){ var mode="
            + json.dumps(mode_js)
            + "; var val="
            + val_js
            + "; var all=document.querySelectorAll('iframe,frame'); var el=null;"
            " if(mode==='index'){ var i=Number(val); el=all[i>=0?i:0]; }"
            " else if(mode==='name'){ for(var k=0;k<all.length;k++){ if(all[k].getAttribute('name')===val){ el=all[k]; break; } } }"
            " else { el=document.evaluate(val,document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue; }"
            " if(!el){ return null; }"
            " var parts=[]; var n=el;"
            " while(n && n.nodeType===1){"
            "  var idx=1; var sib=n.previousElementSibling;"
            "  while(sib){ if(sib.tagName===n.tagName){ idx++; } sib=sib.previousElementSibling; }"
            "  parts.unshift('/'+n.tagName.toLowerCase()+'['+idx+']'); n=n.parentElement;"
            " }"
            " var pos=0; for(var k2=0;k2<all.length;k2++){ if(all[k2]===el){ pos=k2; break; } }"
            " var rect=el.getBoundingClientRect();"
            " return { found:true, xpath:parts.join(''), name:el.getAttribute('name')||'', id:el.getAttribute('id')||'',"
            "  src:el.getAttribute('src')||'', index:pos, count:all.length,"
            "  width:Math.round(rect.width), height:Math.round(rect.height) };"
            " }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, parent_frame)
        if not isinstance(data, dict) or not data.get("found"):
            raise BaseException(WEB_GET_ELE_ERROR.format("iframe 未找到"), "iframe 未找到，请检查定位条件")
        iframe_xpath = data.get("xpath", "")
        if parent_frame is not None:
            iframe_xpath = parent_frame["iframeXpath"] + "/$iframe$/" + iframe_xpath.lstrip("/")
        return {
            "isFrame": True,
            "iframeXpath": iframe_xpath,
            "name": data.get("name", ""),
            "id": data.get("id", ""),
            "src": data.get("src", ""),
            "index": data.get("index", 0),
            "width": data.get("width", 0),
            "height": data.get("height", 0),
        }

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            atomicMg.param("frame", required=False),
        ],
        outputList=[atomicMg.param("current_frame", types="Dict")],
    )
    def switch_iframe(browser_obj: Browser = None, frame: dict = None):
        """切换iframe上下文(传入frame对象切换，留空切换回主文档)。"""
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        if frame is None:
            browser_obj.frame = None
            return {"isFrame": False, "iframeXpath": ""}
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        js_code = (
            "function main(){ return { url: window.location.href, title: document.title, ready: document.readyState }; }"
            + eval_js_code(False)
        )
        BrowserIframe._run_js_in_frame(browser_obj, js_code, effective)
        browser_obj.frame = effective
        return effective

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            _frame_param(),
            _xpath_param(),
        ],
        outputList=[atomicMg.param("text", types="Str")],
    )
    def iframe_get_element_text(browser_obj: Browser = None, frame: dict = None, xpath: str = ""):
        """获取iframe内元素文本(XPath定位)。"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        js_code = (
            "function main(){ var el=document.evaluate("
            + json.dumps(str(xpath), ensure_ascii=False)
            + ",document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;"
            " if(!el){ return null; } return (el.textContent||'').trim(); }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, effective)
        return data if isinstance(data, str) else ""

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            _frame_param(),
            _xpath_param(),
        ],
        outputList=[atomicMg.param("clicked", types="Bool")],
    )
    def iframe_click_element(browser_obj: Browser = None, frame: dict = None, xpath: str = ""):
        """点击iframe内元素(XPath定位，滚动至可见后模拟点击事件)。"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        js_code = (
            "function main(){ var el=document.evaluate("
            + json.dumps(str(xpath), ensure_ascii=False)
            + ",document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;"
            " if(!el){ return {ok:false,msg:'element not found'}; }"
            " try{ if(el.scrollIntoView){ el.scrollIntoView({block:'center',inline:'center'}); } }catch(e){}"
            " try{ el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window})); }catch(e){}"
            " try{ el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window})); }catch(e){}"
            " try{ el.click(); }catch(e){}"
            " try{ el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); }catch(e){}"
            " return {ok:true}; }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, effective)
        if not (isinstance(data, dict) and data.get("ok")):
            raise BaseException(WEB_GET_ELE_ERROR.format("元素未找到"), "iframe 内元素未找到，点击失败")
        return True

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            _frame_param(),
            _xpath_param(),
            atomicMg.param("input_text", types="Str", required=True),
            atomicMg.param("overwrite", types="Bool", required=False),
        ],
        outputList=[atomicMg.param("input_done", types="Bool")],
    )
    def iframe_input_text(
        browser_obj: Browser = None, frame: dict = None, xpath: str = "", input_text: str = "", overwrite: bool = True
    ):
        """向iframe内元素输入文本(XPath定位，支持覆盖/追加)。"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        js_code = (
            "function main(){ var el=document.evaluate("
            + json.dumps(str(xpath), ensure_ascii=False)
            + ",document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;"
            " if(!el){ return {ok:false,msg:'element not found'}; }"
            " var t="
            + json.dumps(str(input_text), ensure_ascii=False)
            + "; var ow="
            + ("true" if overwrite else "false")
            + ";"
            " try{ el.focus(); }catch(e){}"
            " var tag=(el.tagName||'').toUpperCase();"
            " if(tag==='INPUT'||tag==='TEXTAREA'){ el.value=(ow?'':el.value)+t; }"
            " else { el.textContent=(ow?'':(el.textContent||''))+t; }"
            " try{ el.dispatchEvent(new Event('input',{bubbles:true})); }catch(e){}"
            " try{ el.dispatchEvent(new Event('change',{bubbles:true})); }catch(e){}"
            " return {ok:true}; }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, effective)
        if not (isinstance(data, dict) and data.get("ok")):
            raise BaseException(WEB_GET_ELE_ERROR.format("元素未找到"), "iframe 内元素未找到，输入失败")
        return True

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            _frame_param(),
            _xpath_param(),
            atomicMg.param("attribute_name", types="Str", required=False),
        ],
        outputList=[atomicMg.param("similar_list", types="List")],
    )
    def iframe_get_similar_list(
        browser_obj: Browser = None, frame: dict = None, xpath: str = "", attribute_name: str = "text"
    ):
        """获取iframe内相似元素列表(XPath匹配全部元素，提取文本或属性)。"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        js_code = (
            "function main(){ var snap=document.evaluate("
            + json.dumps(str(xpath), ensure_ascii=False)
            + ",document,null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);"
            " var attr=" + json.dumps(str(attribute_name or "text"), ensure_ascii=False) + "; var out=[];"
            " for(var i=0;i<snap.snapshotLength;i++){ var el=snap.snapshotItem(i);"
            "  if(!attr||attr==='text'){ out.push((el.textContent||'').trim()); }"
            "  else if(attr==='html'){ out.push(el.innerHTML||''); }"
            "  else { out.push(el.getAttribute(attr)); } }"
            " return out; }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, effective)
        return data if isinstance(data, list) else []

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            _frame_param(),
            _xpath_param(),
            atomicMg.param("timeout", types="Int", required=False),
            atomicMg.param("wait_status"),
        ],
        outputList=[atomicMg.param("wait_result", types="Bool")],
    )
    def iframe_wait_element(
        browser_obj: Browser = None,
        frame: dict = None,
        xpath: str = "",
        timeout: int = 10,
        wait_status: FrameWaitStatusTypeFlag = FrameWaitStatusTypeFlag.Appear,
    ):
        """等待iframe内元素出现或消失(超时返回False)。"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        timeout = int(timeout) if timeout is not None else 10
        if timeout < 0:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(timeout), "等待时间不能小于0")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        want_disappear = wait_status == FrameWaitStatusTypeFlag.Disappear
        js_code = (
            "function main(){ var xp="
            + json.dumps(str(xpath), ensure_ascii=False)
            + "; var deadline=Date.now()+"
            + str(timeout * 1000)
            + "; var wantDis="
            + ("true" if want_disappear else "false")
            + ";"
            " function exists(){ return !!document.evaluate(xp,document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue; }"
            " return new Promise(function(resolve){"
            "  function tick(){ var found=exists();"
            "   if(found!==wantDis){ resolve(true); return; }"
            "   if(Date.now()>=deadline){ resolve(false); return; }"
            "   setTimeout(tick,200); }"
            "  tick(); }); }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, effective, time_out=float(timeout) + 10)
        return bool(data) if isinstance(data, bool) else data is True

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            _frame_param(),
            _xpath_param(),
            atomicMg.param("attr_name", types="Str", required=True),
        ],
        outputList=[atomicMg.param("attr_value", types="Str")],
    )
    def iframe_get_attribute(browser_obj: Browser = None, frame: dict = None, xpath: str = "", attr_name: str = ""):
        """获取iframe内元素属性值(XPath定位，attr_name支持text/html/任意属性名)。"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        if not attr_name:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "属性名不能为空")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        js_code = (
            "function main(){ var el=document.evaluate("
            + json.dumps(str(xpath), ensure_ascii=False)
            + ",document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;"
            " if(!el){ return null; } var attr=" + json.dumps(str(attr_name), ensure_ascii=False) + ";"
            " if(attr==='text'){ return (el.textContent||'').trim(); }"
            " if(attr==='html'){ return el.innerHTML||''; }"
            " var v=el.getAttribute(attr); return v===null?'':v; }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, effective)
        return data if isinstance(data, str) else ""

    @staticmethod
    @atomicMg.atomic(
        "BrowserIframe",
        inputList=[
            atomicMg.param("browser_obj"),
            _frame_param(),
            _xpath_param(),
        ],
        outputList=[atomicMg.param("element_info", types="Dict")],
    )
    def iframe_get_element_info(browser_obj: Browser = None, frame: dict = None, xpath: str = ""):
        """获取iframe内元素完整信息(标签/文本/属性/位置/可见性)。"""
        if not xpath:
            raise BaseException(PARAMETER_INVALID_FORMAT.format(""), "XPath不能为空")
        browser_obj = BrowserIframe._get_default_browser_or_raise(browser_obj)
        effective = BrowserIframe._resolve_frame(browser_obj, frame)
        js_code = (
            "function main(){ var el=document.evaluate("
            + json.dumps(str(xpath), ensure_ascii=False)
            + ",document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;"
            " if(!el){ return null; }"
            " var attrs={}; for(var i=0;i<el.attributes.length;i++){ attrs[el.attributes[i].name]=el.attributes[i].value; }"
            " var rect=el.getBoundingClientRect(); var cs=getComputedStyle(el);"
            " var visible=!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length)&&cs.visibility!=='hidden'&&cs.display!=='none';"
            " return { tag:(el.tagName||'').toLowerCase(), text:(el.textContent||'').trim(), attributes:attrs,"
            "  rect:{ x:Math.round(rect.x), y:Math.round(rect.y), width:Math.round(rect.width), height:Math.round(rect.height) },"
            "  visible:visible }; }" + eval_js_code(False)
        )
        data = BrowserIframe._run_js_in_frame(browser_obj, js_code, effective)
        if not isinstance(data, dict):
            raise BaseException(WEB_GET_ELE_ERROR.format("元素未找到"), "iframe 内元素未找到")
        return data
