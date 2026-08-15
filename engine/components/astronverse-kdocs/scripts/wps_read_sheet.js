/*
 * WPS AirScript 1.0 script entry.
 *
 * Supported Context.argv fields:
 * - action: read | write | count | first_empty | get_image | insert_image | get_hyperlink | list_sheets | create_sheet | delete_sheet
 *           | replace | copy_paste | insert_cells | delete_cells | clear_range | merge_cells | set_format | get_color
 *           | formula | save_workbook | rename_sheet | move_sheet | auto_fit | get_file_info | calc_function
 * - sheet_name: target worksheet name
 * - range_address: target row / column / range address
 * - read_text: set true to read displayed (formatted) text instead of raw values, only for action=read
 * - write_value: value to write
 * - image_data: image URL or data URI for insert_image
 * - target_type: row | column for count / first_empty
 * - new_sheet_names: target sheet names for create_sheet
 * - find_text / replace_text: search and replace
 * - source_sheet / source_range / target_sheet / target_range: copy_paste
 * - op_type: row | column | cell for insert_cells / delete_cells
 * - clear_type: contents | formats | all for clear_range
 * - merge_type: merge | unmerge for merge_cells
 * - format_options: dict for set_format (font_bold/font_italic/font_size/font_name/font_color/bg_color/h_align/v_align/wrap_text/number_format)
 * - formula_text / write_formula: formula get/set
 * - new_sheet_name: rename_sheet
 * - position: target 1-based position for move_sheet
 * - fit_type: row | column | both for auto_fit
 * - func_name / func_k: sum | average | min | max | large | small for calc_function
 */

function getArgValue(key, defaultValue) {
    if (typeof Context !== "undefined" && Context && Context.argv && typeof Context.argv[key] !== "undefined") {
        return Context.argv[key]
    }

    if (typeof Context !== "undefined" && Context && typeof Context[key] !== "undefined") {
        return Context[key]
    }

    return defaultValue
}

function getParams() {
    let value = getArgValue("new_sheet_names", [])
    let newSheetNames

    if (Array.isArray(value)) {
        newSheetNames = value
    } else if (typeof value === "string" && value.length > 0) {
        newSheetNames = [value]
    } else {
        newSheetNames = []
    }

    return {
        action: String(getArgValue("action", "read")),
        sheetName: String(getArgValue("sheet_name", "")),
        rangeAddress: String(getArgValue("range_address", "")),
        readText: Boolean(getArgValue("read_text", false)),
        writeValue: getArgValue("write_value", ""),
        imageData: String(getArgValue("image_data", "")),
        targetType: String(getArgValue("target_type", "row")).toLowerCase(),
        newSheetNames: newSheetNames,
        findText: String(getArgValue("find_text", "")),
        replaceText: String(getArgValue("replace_text", "")),
        sourceSheet: String(getArgValue("source_sheet", "")),
        sourceRange: String(getArgValue("source_range", "")),
        targetSheet: String(getArgValue("target_sheet", "")),
        targetRangeAddress: String(getArgValue("target_range", "")),
        opType: String(getArgValue("op_type", "row")).toLowerCase(),
        clearType: String(getArgValue("clear_type", "contents")).toLowerCase(),
        mergeType: String(getArgValue("merge_type", "merge")).toLowerCase(),
        formatOptions: getArgValue("format_options", null),
        formulaText: String(getArgValue("formula_text", "")),
        writeFormula: Boolean(getArgValue("write_formula", false)),
        newSheetName: String(getArgValue("new_sheet_name", "")),
        position: getArgValue("position", 1),
        fitType: String(getArgValue("fit_type", "both")).toLowerCase(),
        funcName: String(getArgValue("func_name", "sum")).toLowerCase(),
        funcK: getArgValue("func_k", 1)
    }
}

function getAllSheets() {
    if (typeof Sheets !== "undefined" && Sheets && Sheets.Count > 0) {
        return Sheets
    }
    return Application.Sheets
}

function getWorksheet(sheetName) {
    // Webhook 环境下 Application.Sheets.Item(名称) 可能返回 null，
    // 改为遍历全局 Sheets 逐个比对名称（与 list_sheets 实测可用的方式一致）。
    let sheets = getAllSheets()

    for (let i = 1; i <= sheets.Count; i++) {
        let item = sheets.Item(i)
        if (item && item.Name === sheetName) {
            return item
        }
    }

    let available = []
    for (let j = 1; j <= sheets.Count; j++) {
        available.push(sheets.Item(j).Name)
    }
    throw new Error("工作表[" + sheetName + "]不存在，当前工作簿可用工作表：" + available.join("、"))
}

function getColumnLetters(columnNumber) {
    let result = ""
    let current = Number(columnNumber)
    let remainder

    while (current > 0) {
        remainder = (current - 1) % 26
        result = String.fromCharCode(65 + remainder) + result
        current = Math.floor((current - 1) / 26)
    }

    return result
}

function getReadAddress(curWorksheet, rangeAddress) {
    // 统一把各种输入（""/行号/列字母/A1:B2）换算成显式区域地址
    if (!rangeAddress) {
        let usedRange = curWorksheet.UsedRange
        return getColumnLetters(usedRange.Column) + usedRange.Row + ":" + getColumnLetters(usedRange.ColumnEnd) + usedRange.RowEnd
    }

    if (/^\d+$/.test(rangeAddress)) {
        let usedRange = curWorksheet.UsedRange
        let lastColumnLetter = getColumnLetters(usedRange.ColumnEnd)
        return "A" + rangeAddress + ":" + lastColumnLetter + rangeAddress
    }

    if (/^[A-Za-z]+$/.test(rangeAddress)) {
        let usedRange = curWorksheet.UsedRange
        let columnLetter = String(rangeAddress).toUpperCase()
        return columnLetter + usedRange.Row + ":" + columnLetter + usedRange.RowEnd
    }

    return rangeAddress
}

function isDateFormatString(fmt) {
    // 判断数字格式是否为日期/时间格式；先剔除 [Red]、[DBNum2] 等方括号段避免误判
    let text = String(fmt === null || fmt === undefined ? "" : fmt).replace(/\[[^\]]*\]/g, "")
    if (!text || text.toLowerCase() === "general") {
        return false
    }
    return /[ymdhs]/i.test(text)
}

function resolveDateRangeFlag(fmt) {
    // 多格区域 NumberFormat 可能返回数组，仅当所有格式都是日期时才转换
    if (Array.isArray(fmt)) {
        let flat = []
        let stack = [fmt]
        while (stack.length > 0) {
            let cur = stack.pop()
            if (Array.isArray(cur)) {
                for (let i = 0; i < cur.length; i++) {
                    stack.push(cur[i])
                }
            } else {
                flat.push(cur)
            }
        }
        if (flat.length === 0) {
            return false
        }
        for (let j = 0; j < flat.length; j++) {
            if (!isDateFormatString(flat[j])) {
                return false
            }
        }
        return true
    }
    return isDateFormatString(fmt)
}

function pad2(value) {
    return (value < 10 ? "0" : "") + value
}

function excelSerialToDateString(serial) {
    // Excel 日期序列号从 1899-12-30 起算，25569 对应 1970-01-01
    let ms = Math.round((Number(serial) - 25569) * 86400000)
    if (!isFinite(ms)) {
        return serial
    }

    let date = new Date(ms)
    if (isNaN(date.getTime())) {
        return serial
    }

    let result = date.getUTCFullYear() + "-" + pad2(date.getUTCMonth() + 1) + "-" + pad2(date.getUTCDate())
    if (ms % 86400000 !== 0) {
        result += " " + pad2(date.getUTCHours()) + ":" + pad2(date.getUTCMinutes()) + ":" + pad2(date.getUTCSeconds())
    }
    return result
}

function convertDateValue(value) {
    if (typeof value === "number" && isFinite(value) && value > 0 && value < 2958466) {
        return excelSerialToDateString(value)
    }
    return value
}

function convertMatrixDates(matrix) {
    if (!Array.isArray(matrix)) {
        return convertDateValue(matrix)
    }

    return matrix.map(function (row) {
        if (!Array.isArray(row)) {
            return convertDateValue(row)
        }
        return row.map(convertDateValue)
    })
}

function readRangeSafe(curWorksheet, address) {
    let rangeObj = curWorksheet.Range(address)
    let startRow = rangeObj.Row
    let startColumn = rangeObj.Column
    let endRow = startRow + rangeObj.Rows.Count - 1
    let endColumn = startColumn + rangeObj.Columns.Count - 1
    let isDateRange = false

    // 日期列的 Value2 是序列号（如 46249.46 对应 2026-08-15），先读取数字格式判断
    try {
        isDateRange = resolveDateRangeFlag(rangeObj.NumberFormat)
    } catch (fmtError) {
        isDateRange = false
    }

    try {
        let value = rangeObj.Value2
        return isDateRange ? convertMatrixDates(value) : value
    } catch (e) {
        // 含特殊单元格（如脱敏列）时批量取值会触发内核错误，降级为逐格读取
        if (startRow === endRow && startColumn === endColumn) {
            return null
        }

        let matrix = []
        for (let r = startRow; r <= endRow; r++) {
            let rowValues = []
            for (let c = startColumn; c <= endColumn; c++) {
                try {
                    rowValues.push(curWorksheet.Range(getColumnLetters(c) + r).Value2)
                } catch (cellError) {
                    rowValues.push(null)
                }
            }
            matrix.push(rowValues)
        }
        return isDateRange ? convertMatrixDates(matrix) : matrix
    }
}

function readRangeDisplayText(curWorksheet, address) {
    // 读取显示值模式：逐格读取 .Text（按单元格格式渲染后的文本）
    let rangeObj = curWorksheet.Range(address)
    let startRow = rangeObj.Row
    let startColumn = rangeObj.Column
    let endRow = startRow + rangeObj.Rows.Count - 1
    let endColumn = startColumn + rangeObj.Columns.Count - 1

    if (startRow === endRow && startColumn === endColumn) {
        try {
            return rangeObj.Text
        } catch (e) {
            return null
        }
    }

    let matrix = []
    for (let r = startRow; r <= endRow; r++) {
        let rowValues = []
        for (let c = startColumn; c <= endColumn; c++) {
            try {
                rowValues.push(curWorksheet.Range(getColumnLetters(c) + r).Text)
            } catch (cellError) {
                rowValues.push(null)
            }
        }
        matrix.push(rowValues)
    }
    return matrix
}

function readSheetData(sheetName, rangeAddress, readText) {
    let curWorksheet = getWorksheet(sheetName)
    let address = getReadAddress(curWorksheet, rangeAddress)
    if (readText) {
        return readRangeDisplayText(curWorksheet, address)
    }
    return readRangeSafe(curWorksheet, address)
}

function normalizeWriteMatrix(writeValue) {
    if (!Array.isArray(writeValue)) {
        return null
    }

    if (writeValue.length === 0) {
        return [[]]
    }

    if (Array.isArray(writeValue[0])) {
        return writeValue
    }

    return [writeValue]
}

function writeSheetData(sheetName, rangeAddress, writeValue) {
    let curWorksheet = getWorksheet(sheetName)
    let startAddress = rangeAddress || "A1"
    let startRange = curWorksheet.Range(startAddress)
    let matrix = normalizeWriteMatrix(writeValue)
    let targetRange
    let rowCount
    let columnCount

    if (matrix === null) {
        startRange.Value2 = writeValue
        return startRange.Value2
    }

    rowCount = matrix.length
    columnCount = matrix[0] ? matrix[0].length : 0

    if (rowCount === 0 || columnCount === 0) {
        startRange.Value2 = ""
        return startRange.Value2
    }

    targetRange = startRange.Resize(rowCount, columnCount)
    targetRange.Value2 = matrix
    return targetRange.Value2
}

function getUsedRangeInfo(sheetName) {
    let curWorksheet = getWorksheet(sheetName)
    let usedRange = curWorksheet.UsedRange

    return {
        usedRange: usedRange,
        rowStart: usedRange.Row,
        rowEnd: usedRange.RowEnd,
        columnStart: usedRange.Column,
        columnEnd: usedRange.ColumnEnd,
        rowCount: usedRange.RowEnd - usedRange.Row + 1,
        columnCount: usedRange.ColumnEnd - usedRange.Column + 1
    }
}

function getCountValue(sheetName, targetType) {
    let info = getUsedRangeInfo(sheetName)

    if (targetType === "column") {
        return info.columnCount
    }

    return info.rowCount
}

function getFirstEmptyValue(sheetName, targetType) {
    let info = getUsedRangeInfo(sheetName)

    if (targetType === "column") {
        return getColumnLetters(info.columnEnd + 1)
    }

    return info.rowEnd + 1
}

function getEmbeddedImage(sheetName, rangeAddress) {
    let curWorksheet = getWorksheet(sheetName)
    let targetAddress = rangeAddress || "A1"

    curWorksheet.Range(targetAddress).Select()
    return curWorksheet.Shapes.GetActiveShapeImg()
}

function insertImageToCell(sheetName, rangeAddress, imageData) {
    let curWorksheet = getWorksheet(sheetName)
    let targetAddress = rangeAddress || "A1"
    let targetRange = curWorksheet.Range(targetAddress)

    targetRange.InsertImage(imageData)
    return true
}

function getCellHyperlink(sheetName, rangeAddress) {
    let curWorksheet = getWorksheet(sheetName)
    let targetAddress = rangeAddress || "A1"
    let targetRange = curWorksheet.Range(targetAddress)

    if (targetRange.Hyperlinks.Count > 0) {
        return targetRange.Hyperlinks(1).Address
    }

    return ""
}

function listSheetNames() {
    let list = []

    for (let i = 1; i <= Sheets.Count; i++) {
        list.push(Sheets(i).Name)
    }

    return list
}

function createSheets(newSheetNames) {
    let createdNames = []
    let newSheet
    let curName
    let finalName
    let exists

    for (let i = 0; i < newSheetNames.length; i++) {
        curName = newSheetNames[i]
        newSheet = Sheets.Add()
        finalName = newSheet.Name

        if (typeof curName !== "undefined" && String(curName).length > 0) {
            exists = false
            for (let j = 1; j <= Sheets.Count; j++) {
                if (Sheets(j).Name === curName && Sheets(j).Index !== newSheet.Index) {
                    exists = true
                }
            }

            if (!exists) {
                newSheet.Name = curName
            } else {
                newSheet.Name = curName + "_" + Sheets.Count
            }

            finalName = newSheet.Name
        }

        createdNames.push(finalName)
    }

    return createdNames
}

function deleteSheetByName(sheetName) {
    let targetSheet = getWorksheet(sheetName)
    targetSheet.Delete()
    return true
}

function replaceRangeText(sheetName, rangeAddress, findText, replaceText) {
    if (!findText) {
        throw new Error("查找内容不能为空")
    }

    let curWorksheet = getWorksheet(sheetName)
    let targetRange = rangeAddress ? curWorksheet.Range(rangeAddress) : curWorksheet.UsedRange

    targetRange.Replace(String(findText), String(replaceText || ""))
    return true
}

function copyPasteRange(sourceSheetName, sourceRangeAddress, targetSheetName, targetRangeAddress) {
    let sourceWorksheet = getWorksheet(sourceSheetName)
    let targetWorksheet = getWorksheet(targetSheetName || sourceSheetName)

    sourceWorksheet.Range(sourceRangeAddress || "A1").Copy()
    targetWorksheet.Range(targetRangeAddress || "A1").PasteSpecial()
    return true
}

function insertRowsOrColumns(sheetName, rangeAddress, insertType) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = curWorksheet.Range(rangeAddress || "A1")
    let typeValue = String(insertType || "row").toLowerCase()

    if (typeValue === "row") {
        targetRange.EntireRow.Insert()
    } else if (typeValue === "column") {
        targetRange.EntireColumn.Insert()
    } else {
        targetRange.Insert()
    }
    return true
}

function deleteRowsOrColumns(sheetName, rangeAddress, deleteType) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = curWorksheet.Range(rangeAddress || "A1")
    let typeValue = String(deleteType || "row").toLowerCase()

    if (typeValue === "row") {
        targetRange.EntireRow.Delete()
    } else if (typeValue === "column") {
        targetRange.EntireColumn.Delete()
    } else {
        targetRange.Delete()
    }
    return true
}

function clearRangeContent(sheetName, rangeAddress, clearType) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = rangeAddress ? curWorksheet.Range(rangeAddress) : curWorksheet.UsedRange
    let typeValue = String(clearType || "contents").toLowerCase()

    if (typeValue === "formats") {
        targetRange.ClearFormats()
    } else if (typeValue === "all") {
        targetRange.Clear()
    } else {
        targetRange.ClearContents()
    }
    return true
}

function mergeOrUnmergeCells(sheetName, rangeAddress, mergeType) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = curWorksheet.Range(rangeAddress || "A1")

    if (String(mergeType || "merge").toLowerCase() === "unmerge") {
        targetRange.UnMerge()
    } else {
        targetRange.Merge()
    }
    return true
}

function applyColorSetting(target, hexColor) {
    let hex = String(hexColor).replace("#", "")

    if (hex.length === 3) {
        hex = hex.charAt(0) + hex.charAt(0) + hex.charAt(1) + hex.charAt(1) + hex.charAt(2) + hex.charAt(2)
    }

    let redPart = parseInt(hex.substring(0, 2), 16) || 0
    let greenPart = parseInt(hex.substring(2, 4), 16) || 0
    let bluePart = parseInt(hex.substring(4, 6), 16) || 0

    if (typeof RGB === "function") {
        target.Color = RGB(redPart, greenPart, bluePart)
    } else {
        target.Color = bluePart * 65536 + greenPart * 256 + redPart
    }
}

function getHAlignValue(alignName) {
    let key = String(alignName || "").toLowerCase()
    let enumRef = (typeof Application !== "undefined" && Application.Enum) ? Application.Enum : null

    if (key === "left") return enumRef ? enumRef.XlHAlign.xlHAlignLeft : -4131
    if (key === "center") return enumRef ? enumRef.XlHAlign.xlHAlignCenter : -4108
    if (key === "right") return enumRef ? enumRef.XlHAlign.xlHAlignRight : -4152
    return null
}

function getVAlignValue(alignName) {
    let key = String(alignName || "").toLowerCase()
    let enumRef = (typeof Application !== "undefined" && Application.Enum) ? Application.Enum : null

    if (key === "top") return enumRef ? enumRef.XlVAlign.xlVAlignTop : -4160
    if (key === "center") return enumRef ? enumRef.XlVAlign.xlVAlignCenter : -4108
    if (key === "bottom") return enumRef ? enumRef.XlVAlign.xlVAlignBottom : -4107
    return null
}

function setCellFormat(sheetName, rangeAddress, formatOptions) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = curWorksheet.Range(rangeAddress || "A1")

    if (!formatOptions || typeof formatOptions !== "object") {
        return true
    }

    let key

    for (key in formatOptions) {
        if (!Object.prototype.hasOwnProperty.call(formatOptions, key)) {
            continue
        }

        let value = formatOptions[key]

        if (value === null || value === undefined || value === "") {
            continue
        }

        try {
            if (key === "font_bold") {
                targetRange.Font.Bold = Boolean(value)
            } else if (key === "font_italic") {
                targetRange.Font.Italic = Boolean(value)
            } else if (key === "font_size") {
                targetRange.Font.Size = Number(value)
            } else if (key === "font_name") {
                targetRange.Font.Name = String(value)
            } else if (key === "font_color") {
                applyColorSetting(targetRange.Font, String(value))
            } else if (key === "bg_color") {
                applyColorSetting(targetRange.Interior, String(value))
            } else if (key === "h_align") {
                let hValue = getHAlignValue(value)
                if (hValue !== null) {
                    targetRange.HorizontalAlignment = hValue
                }
            } else if (key === "v_align") {
                let vValue = getVAlignValue(value)
                if (vValue !== null) {
                    targetRange.VerticalAlignment = vValue
                }
            } else if (key === "wrap_text") {
                targetRange.WrapText = Boolean(value)
            } else if (key === "number_format") {
                targetRange.NumberFormat = String(value)
            }
        } catch (formatError) {
            throw new Error("设置格式项[" + key + "]失败: " + (formatError && formatError.message ? formatError.message : formatError))
        }
    }

    return true
}

function colorNumberToHex(colorValue) {
    if (colorValue === null || colorValue === undefined) {
        return ""
    }

    let text = String(colorValue)

    if (text.charAt(0) === "#") {
        return text.toUpperCase()
    }

    let num = Number(colorValue)

    if (isNaN(num)) {
        return text
    }

    let redPart = num & 0xFF
    let greenPart = (num >> 8) & 0xFF
    let bluePart = (num >> 16) & 0xFF
    let to2 = function (v) {
        let s = v.toString(16)
        return s.length === 1 ? "0" + s : s
    }

    return ("#" + to2(redPart) + to2(greenPart) + to2(bluePart)).toUpperCase()
}

function getCellColor(sheetName, rangeAddress) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = curWorksheet.Range(rangeAddress || "A1")

    return {
        bg_color: colorNumberToHex(targetRange.Interior.Color),
        font_color: colorNumberToHex(targetRange.Font.Color)
    }
}

function formulaOperation(sheetName, rangeAddress, formulaText, writeFormula) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = curWorksheet.Range(rangeAddress || "A1")
    let topLeftAddress = getColumnLetters(targetRange.Column) + targetRange.Row
    let cellRange = curWorksheet.Range(topLeftAddress)

    if (writeFormula) {
        if (!formulaText) {
            throw new Error("公式内容不能为空")
        }
        cellRange.Formula = String(formulaText)
    }

    return cellRange.Formula
}

function saveWorkbook() {
    if (typeof Application !== "undefined" && Application.ActiveWorkbook) {
        Application.ActiveWorkbook.Save()
    }
    return true
}

function renameSheetName(sheetName, newSheetName) {
    if (!newSheetName) {
        throw new Error("新工作表名称不能为空")
    }

    let targetSheet = getWorksheet(sheetName)
    targetSheet.Name = String(newSheetName)
    return targetSheet.Name
}

function moveSheetToPosition(sheetName, position) {
    let sheets = getAllSheets()
    let targetSheet = getWorksheet(sheetName)
    let pos = parseInt(position, 10)

    if (isNaN(pos) || pos < 1) {
        pos = 1
    }

    if (pos > sheets.Count) {
        pos = sheets.Count
    }

    if (targetSheet.Index === pos) {
        return true
    }

    if (pos === 1) {
        targetSheet.Move({ Before: sheets.Item(1).Id, After: null })
    } else if (pos >= sheets.Count) {
        targetSheet.Move({ Before: null, After: sheets.Item(sheets.Count).Id })
    } else {
        targetSheet.Move({ Before: sheets.Item(pos).Id, After: null })
    }

    return true
}

function autoFitRange(sheetName, rangeAddress, fitType) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = rangeAddress ? curWorksheet.Range(rangeAddress) : curWorksheet.UsedRange
    let typeValue = String(fitType || "both").toLowerCase()

    if (typeValue === "row") {
        targetRange.EntireRow.AutoFit()
    } else if (typeValue === "column") {
        targetRange.EntireColumn.AutoFit()
    } else {
        targetRange.EntireRow.AutoFit()
        targetRange.EntireColumn.AutoFit()
    }
    return true
}

function getFileInfo() {
    let info = {}

    if (typeof Application !== "undefined" && Application.FileInfo) {
        info.file = Application.FileInfo
    }

    if (typeof Application !== "undefined" && Application.UserInfo) {
        info.user = Application.UserInfo
    }

    return info
}

function calcWorksheetFunction(sheetName, rangeAddress, funcName, k) {
    let curWorksheet = getWorksheet(sheetName)
    let targetRange = curWorksheet.Range(getReadAddress(curWorksheet, rangeAddress))
    let wf = (typeof Application !== "undefined" && Application.WorksheetFunction) ? Application.WorksheetFunction : null

    if (!wf) {
        throw new Error("当前环境不支持 WorksheetFunction")
    }

    if (funcName === "sum") {
        return wf.Sum(targetRange)
    }

    if (funcName === "average") {
        return wf.Average(targetRange)
    }

    if (funcName === "min") {
        return wf.Min(targetRange)
    }

    if (funcName === "max") {
        return wf.Max(targetRange)
    }

    if (funcName === "large") {
        return wf.Large(targetRange, parseInt(k, 10) || 1)
    }

    if (funcName === "small") {
        return wf.Small(targetRange, parseInt(k, 10) || 1)
    }

    throw new Error("不支持的函数: " + funcName + "，支持 sum/average/min/max/large/small")
}

function Macro() {
    let params = getParams()

    if (params.action === "write") {
        return writeSheetData(params.sheetName, params.rangeAddress, params.writeValue)
    }

    if (params.action === "count") {
        return getCountValue(params.sheetName, params.targetType)
    }

    if (params.action === "first_empty") {
        return getFirstEmptyValue(params.sheetName, params.targetType)
    }

    if (params.action === "get_image") {
        return getEmbeddedImage(params.sheetName, params.rangeAddress)
    }

    if (params.action === "insert_image") {
        return insertImageToCell(params.sheetName, params.rangeAddress, params.imageData)
    }

    if (params.action === "get_hyperlink") {
        return getCellHyperlink(params.sheetName, params.rangeAddress)
    }

    if (params.action === "list_sheets") {
        return listSheetNames()
    }

    if (params.action === "create_sheet") {
        return createSheets(params.newSheetNames)
    }

    if (params.action === "delete_sheet") {
        return deleteSheetByName(params.sheetName)
    }

    if (params.action === "replace") {
        return replaceRangeText(params.sheetName, params.rangeAddress, params.findText, params.replaceText)
    }

    if (params.action === "copy_paste") {
        return copyPasteRange(params.sourceSheet, params.sourceRange, params.targetSheet, params.targetRangeAddress)
    }

    if (params.action === "insert_cells") {
        return insertRowsOrColumns(params.sheetName, params.rangeAddress, params.opType)
    }

    if (params.action === "delete_cells") {
        return deleteRowsOrColumns(params.sheetName, params.rangeAddress, params.opType)
    }

    if (params.action === "clear_range") {
        return clearRangeContent(params.sheetName, params.rangeAddress, params.clearType)
    }

    if (params.action === "merge_cells") {
        return mergeOrUnmergeCells(params.sheetName, params.rangeAddress, params.mergeType)
    }

    if (params.action === "set_format") {
        return setCellFormat(params.sheetName, params.rangeAddress, params.formatOptions)
    }

    if (params.action === "get_color") {
        return getCellColor(params.sheetName, params.rangeAddress)
    }

    if (params.action === "formula") {
        return formulaOperation(params.sheetName, params.rangeAddress, params.formulaText, params.writeFormula)
    }

    if (params.action === "save_workbook") {
        return saveWorkbook()
    }

    if (params.action === "rename_sheet") {
        return renameSheetName(params.sheetName, params.newSheetName)
    }

    if (params.action === "move_sheet") {
        return moveSheetToPosition(params.sheetName, params.position)
    }

    if (params.action === "auto_fit") {
        return autoFitRange(params.sheetName, params.rangeAddress, params.fitType)
    }

    if (params.action === "get_file_info") {
        return getFileInfo()
    }

    if (params.action === "calc_function") {
        return calcWorksheetFunction(params.sheetName, params.rangeAddress, params.funcName, params.funcK)
    }

    return readSheetData(params.sheetName, params.rangeAddress, params.readText)
}

let result = Macro()
console.log(result)
return result
