from astronverse.websocket_client.ws_client import WsApp


def _make_app():
    # log 置空，避免测试输出；构造函数不建立任何网络连接
    return WsApp(url="ws://127.0.0.1:1/not-used", log=lambda *args, **kwargs: None)


def test_invalid_message_is_not_dispatched():
    """非法消息（JSON 解析失败）应被丢弃，不应再投递到线程池触发 NameError。"""
    app = _make_app()

    submitted = []

    # 只记录被投递的任务，不真正执行，避免对线程池产生副作用
    app.thread_pool.submit = lambda fn, *args, **kwargs: submitted.append(fn)

    app._on_message(ws=None, message="not-a-json-message")

    # 解析失败后必须提前返回，不能调度 inner_on_message
    assert submitted == [], "invalid message was dispatched to the worker pool"

    app.thread_pool.shutdown(wait=False)


def test_valid_message_is_still_dispatched():
    """合法消息必须照常投递到线程池，保证正常路径不受影响。"""
    app = _make_app()

    submitted = []
    app.thread_pool.submit = lambda fn, *args, **kwargs: submitted.append(fn)

    app._on_message(ws=None, message='{"channel": "ping"}')

    assert len(submitted) == 1, "valid message was not dispatched"

    app.thread_pool.shutdown(wait=False)
