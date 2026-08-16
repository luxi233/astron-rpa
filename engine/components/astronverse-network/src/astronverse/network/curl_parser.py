"""curl 命令解析器: 将 Chrome「Copy as cURL」/Fiddler/Postman 导出的 curl 命令解析为请求参数"""

import json
import shlex


def _split_curl_command(curl_text: str):
    """切分 curl 命令(兼容 posix 单引号与 Windows cmd 未加引号的续行)"""
    text = curl_text.strip()
    if text.startswith("curl "):
        text = text[5:]
    # 去掉反斜杠续行
    text = text.replace("\\\r\n", " ").replace("\\\n", " ").replace("\\\r", " ")
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        # 引号不成对等场景退化为空白切分
        return text.split()


def parse_curl(curl_text: str) -> dict:
    """解析 curl 命令, 返回 {url, method, headers(dict), body, body_type}

    支持: -H/--header, -X/--request, -d/--data/--data-raw/--data-binary/--data-urlencode,
          -u/--user(Basic认证), -b/--cookie, -G(参数转查询串, 退化为GET), --compressed/-k 等忽略
    """
    tokens = _split_curl_command(curl_text)
    result = {"url": "", "method": None, "headers": {}, "body": "", "body_type": None}
    i = 0
    data_params = []
    while i < len(tokens):
        token = tokens[i]

        def next_value():
            nonlocal i
            i += 1
            return tokens[i] if i < len(tokens) else ""

        if token in ("-H", "--header"):
            header = next_value()
            if ":" in header:
                name, _, value = header.partition(":")
                result["headers"][name.strip()] = value.strip()
        elif token in ("-X", "--request"):
            result["method"] = next_value().upper()
        elif token in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"):
            result["body"] = next_value()
            result["body_type"] = "data"
            data_params.append(result["body"])
        elif token in ("-u", "--user"):
            user_info = next_value()
            import base64

            cred = base64.b64encode(user_info.encode("utf-8")).decode("ascii")
            result["headers"]["Authorization"] = "Basic {}".format(cred)
        elif token in ("-b", "--cookie"):
            cookie = next_value()
            if "=" in cookie or ";" in cookie:
                result["headers"].setdefault("Cookie", cookie)
        elif token == "-F" or token == "--form":
            form = next_value()
            result["body_type"] = "form"
            data_params.append(form)
        elif token == "-G" or token == "--get":
            result["method"] = "GET"
        elif token in ("-A", "--user-agent"):
            result["headers"]["User-Agent"] = next_value()
        elif token in ("-e", "--referer"):
            result["headers"]["Referer"] = next_value()
        elif token.startswith("-"):
            # 忽略 -k/--compressed/--location/-s/-i/-v/-L/--insecure/--no-buffer 等
            known_no_value = {
                "-k",
                "--insecure",
                "--compressed",
                "-s",
                "--silent",
                "-i",
                "--include",
                "-v",
                "--verbose",
                "-L",
                "--location",
                "-4",
                "-6",
                "-#",
                "--progress-bar",
                "-f",
                "--fail",
                "-S",
                "--show-error",
                "--no-buffer",
                "-g",
                "--globoff",
            }
            known_with_value = {
                "--max-time",
                "-m",
                "--connect-timeout",
                "--output",
                "-o",
                "--url",
                "--retry",
                "-x",
                "--proxy",
                "--cert",
                "--key",
                "--cacert",
                "-T",
                "--upload-file",
                "-c",
                "--cookie-jar",
            }
            if token in known_with_value:
                next_value()
            elif token not in known_no_value and not token.startswith("--data"):
                # 未知带值选项尽力跳过
                next_value()
        else:
            # 位置参数: 第一个视为 URL
            if token and not result["url"]:
                result["url"] = token

        i += 1

    # 默认: 有 body 且未显式指定方法 → POST; 否则 GET
    if not result["method"]:
        result["method"] = "POST" if result["body"] else "GET"

    # -d 多段合并(等价 curl 行为: & 拼接)
    if result["body_type"] == "data" and len(data_params) > 1:
        result["body"] = "&".join(data_params)

    if result["body"] and result["body_type"] == "data":
        result["headers"].setdefault("Content-Type", "application/x-www-form-urlencoded")

    return result


def parse_curl_summary(curl_text: str) -> str:
    """解析 curl 并生成人类可读摘要(用于日志/调试输出)"""
    parsed = parse_curl(curl_text)
    headers = json.dumps(parsed["headers"], ensure_ascii=False)
    body = (parsed["body"] or "")[:200]
    return "{} {} headers={} body={}".format(parsed["method"], parsed["url"], headers, body)
