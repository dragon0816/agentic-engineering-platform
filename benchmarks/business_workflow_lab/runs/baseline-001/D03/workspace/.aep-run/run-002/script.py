import importlib.util
mods=['pyautogui','pywinauto','uiautomation','pandas','openpyxl']
for m in mods:
 print(m, importlib.util.find_spec(m))
