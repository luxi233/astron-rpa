from enum import Enum


class TokenType(Enum):
    EOF = "EOF"

    Break = "Code.Break"
    Continue = "Code.Continue"
    Return = "Code.Return"

    If = "Code.If"
    IfMulti = "Code.IfMulti"
    ElseIf = "Code.ElseIf"
    ElseIfMulti = "Code.ElseIfMulti"
    Else = "Code.Else"

    IfEnd = "Code.IfEnd"

    While = "Code.While"
    Infinite = "Code.Infinite"
    ForStep = "Code.ForStep"
    ForList = "Code.ForList"
    ForDict = "Code.ForDict"

    ForEnd = "Code.ForEnd"

    Try = "Code.Try"
    Catch = "Code.Catch"
    Finally = "Code.Finally"
    TryEnd = "Code.TryEnd"

    Group = "Code.Group"
    GroupEnd = "Code.GroupEnd"

    @classmethod
    def to_dict(cls):
        return {item.value: item.value for item in cls}


token_type_key_dict = TokenType.to_dict()

special_token_type_end = {
    TokenType.If.value: [
        TokenType.Else.value,
        TokenType.ElseIf.value,
        TokenType.ElseIfMulti.value,
        TokenType.IfEnd.value,
    ],
    TokenType.IfMulti.value: [
        TokenType.Else.value,
        TokenType.ElseIf.value,
        TokenType.ElseIfMulti.value,
        TokenType.IfEnd.value,
    ],
    TokenType.Else.value: [TokenType.IfEnd.value],
    TokenType.ElseIf.value: [
        TokenType.Else.value,
        TokenType.ElseIf.value,
        TokenType.ElseIfMulti.value,
        TokenType.IfEnd.value,
    ],
    TokenType.ElseIfMulti.value: [
        TokenType.Else.value,
        TokenType.ElseIf.value,
        TokenType.ElseIfMulti.value,
        TokenType.IfEnd.value,
    ],
    TokenType.Try.value: [TokenType.Catch.value],
    TokenType.Catch.value: [TokenType.Finally.value, TokenType.TryEnd.value],
    TokenType.Finally.value: [TokenType.TryEnd.value],
    TokenType.ForStep.value: [TokenType.ForEnd.value],
    TokenType.ForList.value: [TokenType.ForEnd.value],
    TokenType.ForDict.value: [TokenType.ForEnd.value],
    TokenType.While.value: [TokenType.ForEnd.value],
    TokenType.Infinite.value: [TokenType.ForEnd.value],
}

exist_atomic_dict = [
    "CV.is_image_exist",
    "File.file_exist",
    "Folder.folder_exist",
    "Window.exist",
    "BrowserElement.element_visible",
    "BrowserElement.text_exist",
    "WinEle.contain_element",
    "CV.ocr_text_exist",
]

for_atomic_dict = [
    "Excel.loop_excel_content",
    "BrowserElement.loop_similar",
    "DataTable.loop_data_table",
    "WinEle.loop_similar",
]
