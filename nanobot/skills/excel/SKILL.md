---
name: excel
description: "Excel 报表处理：读取、分析、合并、生成 Excel 文件。支持多表合并、数据透视、筛选统计等操作。"
metadata: {"nanobot":{"emoji":"📊","requires":{"python":["pandas","openpyxl","xlsxwriter"]},"install":[{"id":"pip","kind":"pip","packages":["pandas","openpyxl","xlsxwriter"],"label":"Install Excel dependencies (pip)"}]}}
---

# Excel Skill

使用 pandas + openpyxl 处理 Excel 文件。所有操作通过 `exec` 工具执行 Python 代码完成。

## 依赖

```bash
pip install pandas openpyxl xlsxwriter
```

## 读取 Excel

```python
import pandas as pd

# 读取单个文件
df = pd.read_excel("/path/to/file.xlsx")
print(df.head())
print(df.describe())

# 读取指定 sheet
df = pd.read_excel("/path/to/file.xlsx", sheet_name="Sheet2")

# 读取所有 sheet（返回 dict）
sheets = pd.read_excel("/path/to/file.xlsx", sheet_name=None)
for name, df in sheets.items():
    print(f"--- {name} ---")
    print(df.head())
```

## 合并多个 Excel

```python
import pandas as pd
from pathlib import Path

# 合并同目录下所有 xlsx 文件
files = list(Path("/path/to/dir").glob("*.xlsx"))
dfs = [pd.read_excel(f) for f in files]
merged = pd.concat(dfs, ignore_index=True)
merged.to_excel("/path/to/merged.xlsx", index=False, engine="xlsxwriter")
print(f"合并完成: {len(files)} 个文件, 共 {len(merged)} 行")
```

## 数据分析与统计

```python
import pandas as pd

df = pd.read_excel("/path/to/file.xlsx")

# 基本统计
print(df.describe())

# 按列分组统计
print(df.groupby("部门")["金额"].agg(["sum", "mean", "count"]))

# 数据透视表
pivot = pd.pivot_table(df, values="金额", index="部门", columns="月份", aggfunc="sum")
print(pivot)
```

## 筛选与过滤

```python
import pandas as pd

df = pd.read_excel("/path/to/file.xlsx")

# 条件筛选
filtered = df[df["金额"] > 10000]

# 多条件
filtered = df[(df["部门"] == "销售") & (df["金额"] > 5000)]

# 去重
deduped = df.drop_duplicates(subset=["姓名", "日期"])

# 保存结果
filtered.to_excel("/path/to/output.xlsx", index=False, engine="xlsxwriter")
```

## 生成新报表

```python
import pandas as pd

# 从零创建
data = {
    "姓名": ["张三", "李四", "王五"],
    "部门": ["技术", "销售", "财务"],
    "金额": [8000, 12000, 9500],
}
df = pd.DataFrame(data)
df.to_excel("/path/to/report.xlsx", index=False, engine="xlsxwriter")

# 多 sheet 写入
with pd.ExcelWriter("/path/to/report.xlsx", engine="xlsxwriter") as writer:
    df1.to_excel(writer, sheet_name="汇总", index=False)
    df2.to_excel(writer, sheet_name="明细", index=False)
```

## 格式化输出

```python
import pandas as pd

with pd.ExcelWriter("/path/to/styled.xlsx", engine="xlsxwriter") as writer:
    df.to_excel(writer, sheet_name="报表", index=False)
    workbook = writer.book
    worksheet = writer.sheets["报表"]

    # 设置列宽
    for i, col in enumerate(df.columns):
        max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
        worksheet.set_column(i, i, max_len)

    # 添加表头格式
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#4472C4", "font_color": "white"})
    for i, col in enumerate(df.columns):
        worksheet.write(0, i, col, header_fmt)
```

## 注意事项

- 读取 `.xlsx` 用 `openpyxl` 引擎（默认）
- 读取 `.xls` 旧格式需要额外安装 `xlrd`
- 写入推荐用 `engine="xlsxwriter"`，格式化能力更强
- 大文件（>10万行）注意内存，可用 `chunksize` 分块读取
- 输出文件路径建议用绝对路径，方便后续通过 MEDIA 标记发送给用户
