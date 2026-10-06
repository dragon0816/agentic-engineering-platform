from pathlib import Path
import openpyxl
wb=openpyxl.load_workbook('input/project_template.xlsx', data_only=False)
ws=wb['Instructions']
for row in ws.iter_rows(values_only=True):
    print(row)
