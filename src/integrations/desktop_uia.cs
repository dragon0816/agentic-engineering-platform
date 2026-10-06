// Desktop UI Automation helper for `desktop/operate` (lab gap L2).
//
// One process per call: reads one JSON request on stdin, operates the windows
// of one process through System.Windows.Automation (built into .NET
// Framework), writes one JSON result on stdout and exits.
//
// Request: {"pid": int, "window": "<title substring, or empty for the pid's
//           main window>", "actions": [...], "look": bool}
// Result:  {"ok": true, "data": {...}, "look": {...}} or
//          {"ok": false, "code": "<snake_case>", "message": "...", "step": n}
//
// Controls are addressed by AutomationId (a WinForms control's Name). Lessons
// from driving the lab Expense app that this helper encodes:
// - InvokePattern.Invoke on a WinForms button does not return while a modal
//   dialog it opened is up, so invoke runs on a worker thread and the helper
//   waits until the click either finished or put up a dialog.
// - While a modal dialog is open its owner reports IsEnabled=false and invoking
//   it fails ("Hot key is already registered"), so every control call first
//   waits for the control to be enabled, and dismiss waits for the box to go.
// - Owned windows (message boxes, modal forms, Save As) appear as Window
//   children of their owner in the UIA tree.
// - A DropDownList combobox has no ValuePattern: select its ListItem by name.
// - A Details-view ListView is a DataGrid of DataItem rows; GridPattern and
//   TablePattern give the cells and the column headers.
// - A multi-line edit has TextPattern but no ValuePattern.
// - The common Save As dialog: file name edit AutomationId 1001, Save button 1.
//
// Build (desktop.py does this): csc /codepage:65001 /target:exe
//   /r:WPF\UIAutomationClient.dll /r:WPF\UIAutomationTypes.dll
//   /r:System.Web.Extensions.dll desktop_uia.cs

using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;

namespace AepDesktop
{
    internal sealed class Refusal : Exception
    {
        public readonly string Code;

        public Refusal(string code, string message) : base(message)
        {
            Code = code;
        }
    }

    internal sealed class Session
    {
        private const int MaxControls = 120;
        private const int MaxTexts = 20;
        private const int MaxValueChars = 300;

        private readonly int pid;
        private readonly string windowTitle;
        private AutomationElement main;
        private Dictionary<string, AutomationElement> mainControls;
        public readonly Dictionary<string, object> Data = new Dictionary<string, object>();

        public Session(int pid, string windowTitle)
        {
            this.pid = pid;
            this.windowTitle = windowTitle ?? "";
        }

        // ---------------------------------------------------------------- windows

        private static Condition WindowCondition()
        {
            return new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Window);
        }

        private List<AutomationElement> TopWindows()
        {
            List<AutomationElement> found = new List<AutomationElement>();
            Condition condition = new AndCondition(
                new PropertyCondition(AutomationElement.ProcessIdProperty, pid), WindowCondition());
            foreach (AutomationElement window in AutomationElement.RootElement.FindAll(TreeScope.Children, condition))
                found.Add(window);
            return found;
        }

        public AutomationElement Main()
        {
            if (main != null)
            {
                try
                {
                    string probe = main.Current.Name;
                    return main;
                }
                catch (ElementNotAvailableException)
                {
                    main = null;
                    mainControls = null;
                }
            }
            DateTime deadline = DateTime.UtcNow.AddSeconds(20);
            while (true)
            {
                foreach (AutomationElement window in TopWindows())
                {
                    string name = SafeName(window);
                    if (windowTitle.Length == 0 || name.IndexOf(windowTitle, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        main = window;
                        return main;
                    }
                }
                if (DateTime.UtcNow > deadline)
                    throw new Refusal("window_missing", "no window of process " + pid
                        + (windowTitle.Length > 0 ? " titled like '" + windowTitle + "'" : ""));
                Thread.Sleep(250);
            }
        }

        // Open dialogs of the process, most recently nested first: Window
        // children (and grandchildren) of the main window, then other top-level
        // windows of the process.
        public List<AutomationElement> Dialogs()
        {
            List<AutomationElement> result = new List<AutomationElement>();
            AutomationElement root = Main();
            try
            {
                foreach (AutomationElement child in root.FindAll(TreeScope.Children, WindowCondition()))
                {
                    foreach (AutomationElement grandchild in child.FindAll(TreeScope.Children, WindowCondition()))
                        result.Add(grandchild);
                    result.Add(child);
                }
                foreach (AutomationElement window in TopWindows())
                {
                    if (!Automation.Compare(window, root)) result.Add(window);
                }
            }
            catch (ElementNotAvailableException)
            {
                // A dialog closed while being listed; the caller polls again.
            }
            return result;
        }

        public AutomationElement WaitDialog(string title, double seconds)
        {
            DateTime deadline = DateTime.UtcNow.AddSeconds(seconds);
            while (true)
            {
                foreach (AutomationElement dialog in Dialogs())
                {
                    string name = SafeName(dialog);
                    if (string.IsNullOrEmpty(title) || name.IndexOf(title, StringComparison.OrdinalIgnoreCase) >= 0)
                        return dialog;
                }
                if (DateTime.UtcNow > deadline)
                    throw new Refusal("dialog_missing", string.IsNullOrEmpty(title)
                        ? "no dialog is open" : "no dialog titled like '" + title + "'");
                Thread.Sleep(150);
            }
        }

        private bool IsOpen(AutomationElement window)
        {
            foreach (AutomationElement dialog in Dialogs())
                if (Automation.Compare(dialog, window)) return true;
            return false;
        }

        private bool WaitClosed(AutomationElement window, double seconds)
        {
            DateTime deadline = DateTime.UtcNow.AddSeconds(seconds);
            while (DateTime.UtcNow < deadline)
            {
                if (!IsOpen(window)) return true;
                Thread.Sleep(150);
            }
            return !IsOpen(window);
        }

        // ---------------------------------------------------------------- controls

        // Controls of a window by AutomationId, not descending into owned windows.
        private static void Collect(AutomationElement parent, Dictionary<string, AutomationElement> into,
            List<AutomationElement> ordered, int depth)
        {
            if (depth > 25) return;
            TreeWalker walker = TreeWalker.ControlViewWalker;
            AutomationElement child = walker.GetFirstChild(parent);
            while (child != null)
            {
                ControlType type = child.Current.ControlType;
                if (type != ControlType.Window && type != ControlType.TitleBar && type != ControlType.MenuBar)
                {
                    string id = child.Current.AutomationId;
                    if (!string.IsNullOrEmpty(id) && !into.ContainsKey(id))
                    {
                        into[id] = child;
                        if (ordered != null) ordered.Add(child);
                    }
                    // Rows and list items are read through their list, not one by one.
                    if (type != ControlType.DataGrid && type != ControlType.List && type != ControlType.ComboBox
                        && type != ControlType.Tree && type != ControlType.Table)
                        Collect(child, into, ordered, depth + 1);
                }
                child = walker.GetNextSibling(child);
            }
        }

        private Dictionary<string, AutomationElement> MainControls(bool refresh)
        {
            if (mainControls == null || refresh)
            {
                mainControls = new Dictionary<string, AutomationElement>();
                Collect(Main(), mainControls, null, 0);
            }
            return mainControls;
        }

        // A control by AutomationId: open dialogs first (a modal form's own
        // controls), then the main window.
        public AutomationElement Control(string id)
        {
            if (string.IsNullOrEmpty(id)) throw new Refusal("control_missing", "an action needs an id");
            Condition byId = new PropertyCondition(AutomationElement.AutomationIdProperty, id);
            foreach (AutomationElement dialog in Dialogs())
            {
                try
                {
                    AutomationElement found = dialog.FindFirst(TreeScope.Descendants, byId);
                    if (found != null) return found;
                }
                catch (ElementNotAvailableException)
                {
                }
            }
            AutomationElement element;
            if (MainControls(false).TryGetValue(id, out element) && Alive(element)) return element;
            if (MainControls(true).TryGetValue(id, out element)) return element;
            throw new Refusal("control_missing", "no control with id '" + id + "'");
        }

        private static bool Alive(AutomationElement element)
        {
            try
            {
                string probe = element.Current.AutomationId;
                return true;
            }
            catch (ElementNotAvailableException)
            {
                return false;
            }
        }

        private static string SafeName(AutomationElement element)
        {
            try
            {
                return element.Current.Name ?? "";
            }
            catch (ElementNotAvailableException)
            {
                return "";
            }
        }

        private static void WaitEnabled(AutomationElement element, string id, double seconds)
        {
            DateTime deadline = DateTime.UtcNow.AddSeconds(seconds);
            while (!element.Current.IsEnabled)
            {
                if (DateTime.UtcNow > deadline)
                    throw new Refusal("not_enabled", "control '" + id + "' is not enabled");
                Thread.Sleep(150);
            }
        }

        private static object Pattern(AutomationElement element, AutomationPattern pattern)
        {
            object found;
            return element.TryGetCurrentPattern(pattern, out found) ? found : null;
        }

        // ---------------------------------------------------------------- actions

        public void Run(Dictionary<string, object> action)
        {
            string kind = Str(action, "do");
            switch (kind)
            {
                case "set": Set(Str(action, "id"), Str(action, "value") ?? ""); break;
                case "invoke": Invoke(Str(action, "id")); break;
                case "select_row": SelectRow(Str(action, "id"), Str(action, "name")); break;
                case "read": Read(Str(action, "id"), Str(action, "save_as")); break;
                case "read_table": ReadTable(Str(action, "id"), Str(action, "save_as")); break;
                case "dialog": DialogAction(Str(action, "save_as"), Num(action, "seconds", 5)); break;
                case "dismiss": Dismiss(Str(action, "button"), Num(action, "seconds", 5)); break;
                case "clear_dialogs": ClearDialogs(); break;
                case "save_as": SaveAs(Str(action, "path"), Num(action, "seconds", 15)); break;
                case "wait_dialog": WaitDialog(Str(action, "title"), Num(action, "seconds", 10)); break;
                case "wait": Thread.Sleep((int)(Math.Min(Math.Max(Num(action, "seconds", 1), 0), 60) * 1000)); break;
                default: throw new Refusal("action_unknown", "unknown action '" + kind + "'");
            }
        }

        private void Set(string id, string value)
        {
            AutomationElement element = Control(id);
            WaitEnabled(element, id, 10);
            if (element.Current.ControlType == ControlType.ComboBox)
            {
                Condition item = new AndCondition(
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.ListItem),
                    new PropertyCondition(AutomationElement.NameProperty, value));
                AutomationElement choice = element.FindFirst(TreeScope.Descendants, item);
                if (choice == null)
                {
                    // An editable combobox takes any text through its ValuePattern.
                    ValuePattern editable = Pattern(element, ValuePattern.Pattern) as ValuePattern;
                    if (editable == null || editable.Current.IsReadOnly)
                        throw new Refusal("item_missing", "combobox '" + id + "' has no item '" + value + "'");
                    editable.SetValue(value);
                    return;
                }
                SelectionItemPattern select = Pattern(choice, SelectionItemPattern.Pattern) as SelectionItemPattern;
                if (select == null) throw new Refusal("pattern_unsupported", "item cannot be selected");
                select.Select();
                return;
            }
            ValuePattern pattern = Pattern(element, ValuePattern.Pattern) as ValuePattern;
            if (pattern == null)
                throw new Refusal("pattern_unsupported", "control '" + id + "' does not take a value");
            if (pattern.Current.IsReadOnly) throw new Refusal("not_enabled", "control '" + id + "' is read-only");
            pattern.SetValue(value);
        }

        // Fire Invoke on a worker thread; return once it finished or once it put
        // up a dialog (its handler then waits for that dialog).
        private void InvokeElement(AutomationElement element, string id)
        {
            WaitEnabled(element, id, 10);
            InvokePattern pattern = Pattern(element, InvokePattern.Pattern) as InvokePattern;
            if (pattern == null) throw new Refusal("pattern_unsupported", "control '" + id + "' cannot be invoked");
            int before = Dialogs().Count;
            string failure = null;
            ManualResetEvent done = new ManualResetEvent(false);
            ThreadPool.QueueUserWorkItem(delegate
            {
                try
                {
                    pattern.Invoke();
                }
                catch (Exception error)
                {
                    failure = error.GetType().Name + ": " + error.Message;
                }
                finally
                {
                    done.Set();
                }
            });
            DateTime deadline = DateTime.UtcNow.AddSeconds(15);
            while (DateTime.UtcNow < deadline)
            {
                if (done.WaitOne(200))
                {
                    if (failure != null && failure.StartsWith("ElementNotEnabled", StringComparison.Ordinal))
                        throw new Refusal("not_enabled", "control '" + id + "' is not enabled");
                    if (failure != null && !failure.StartsWith("ElementNotAvailable", StringComparison.Ordinal))
                        throw new Refusal("invoke_failed", failure);
                    return;
                }
                if (Dialogs().Count > before) return;
            }
            // Neither finished nor a dialog: a slow handler; the caller can look or wait.
        }

        private void Invoke(string id)
        {
            InvokeElement(Control(id), id);
        }

        private static AutomationElementCollection Rows(AutomationElement list)
        {
            Condition rows = new OrCondition(
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.DataItem),
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.ListItem));
            return list.FindAll(TreeScope.Children, rows);
        }

        private void SelectRow(string id, string name)
        {
            AutomationElement list = Control(id);
            WaitEnabled(list, id, 10);
            foreach (AutomationElement row in Rows(list))
            {
                if (row.Current.Name == name)
                {
                    SelectionItemPattern select = Pattern(row, SelectionItemPattern.Pattern) as SelectionItemPattern;
                    if (select == null) throw new Refusal("pattern_unsupported", "row cannot be selected");
                    select.Select();
                    return;
                }
            }
            throw new Refusal("row_missing", "list '" + id + "' has no row '" + name + "'");
        }

        public static string ValueOf(AutomationElement element)
        {
            ValuePattern value = Pattern(element, ValuePattern.Pattern) as ValuePattern;
            if (value != null) return value.Current.Value ?? "";
            TextPattern text = Pattern(element, TextPattern.Pattern) as TextPattern;
            if (text != null) return text.DocumentRange.GetText(-1) ?? "";
            SelectionPattern selection = Pattern(element, SelectionPattern.Pattern) as SelectionPattern;
            if (selection != null && element.Current.ControlType == ControlType.ComboBox)
            {
                List<string> names = new List<string>();
                foreach (AutomationElement item in selection.Current.GetSelection()) names.Add(SafeName(item));
                return string.Join(", ", names);
            }
            return SafeName(element);
        }

        private void Read(string id, string saveAs)
        {
            Data[string.IsNullOrEmpty(saveAs) ? id : saveAs] = ValueOf(Control(id));
        }

        private void ReadTable(string id, string saveAs)
        {
            AutomationElement list = Control(id);
            List<string> headers = new List<string>();
            TablePattern table = Pattern(list, TablePattern.Pattern) as TablePattern;
            if (table != null)
                foreach (AutomationElement header in table.Current.GetColumnHeaders()) headers.Add(SafeName(header));
            if (headers.Count == 0)
            {
                Condition headerItems = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.HeaderItem);
                foreach (AutomationElement header in list.FindAll(TreeScope.Descendants, headerItems))
                    headers.Add(SafeName(header));
            }
            List<object> rows = new List<object>();
            GridPattern grid = Pattern(list, GridPattern.Pattern) as GridPattern;
            if (grid != null && headers.Count > 0)
            {
                int count = grid.Current.RowCount;
                int columns = Math.Min(grid.Current.ColumnCount, headers.Count);
                for (int r = 0; r < count; r++)
                {
                    Dictionary<string, object> row = new Dictionary<string, object>();
                    for (int c = 0; c < columns; c++)
                    {
                        AutomationElement cell = grid.GetItem(r, c);
                        row[headers[c]] = cell == null ? "" : ValueOf(cell);
                    }
                    rows.Add(row);
                }
            }
            else
            {
                foreach (AutomationElement item in Rows(list))
                {
                    Dictionary<string, object> row = new Dictionary<string, object>();
                    row[headers.Count > 0 ? headers[0] : "Name"] = SafeName(item);
                    rows.Add(row);
                }
            }
            Data[string.IsNullOrEmpty(saveAs) ? id : saveAs] = rows;
        }

        public Dictionary<string, object> Describe(AutomationElement dialog, int budget)
        {
            Dictionary<string, object> described = new Dictionary<string, object>();
            described["title"] = SafeName(dialog);
            List<object> texts = new List<object>();
            List<object> buttons = new List<object>();
            try
            {
                Condition text = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Text);
                foreach (AutomationElement item in dialog.FindAll(TreeScope.Descendants, text))
                {
                    string name = SafeName(item);
                    if (name.Length > 0 && texts.Count < MaxTexts) texts.Add(Clip(name));
                }
                Condition button = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
                foreach (AutomationElement item in dialog.FindAll(TreeScope.Descendants, button))
                {
                    TreeWalker walker = TreeWalker.ControlViewWalker;
                    AutomationElement parent = walker.GetParent(item);
                    if (parent != null && parent.Current.ControlType == ControlType.TitleBar) continue;
                    buttons.Add(SafeName(item));
                }
            }
            catch (ElementNotAvailableException)
            {
            }
            described["texts"] = texts;
            described["buttons"] = buttons;
            // A message box's own parts are already its texts and buttons; list
            // controls only for a dialog that has something else (a modal form).
            List<object> controls = new List<object>();
            bool useful = false;
            foreach (object item in Controls(dialog, budget))
            {
                Dictionary<string, object> control = (Dictionary<string, object>)item;
                string type = (string)control["type"];
                if (type == "Image" || type == "Text") continue;
                if (type != "Button") useful = true;
                controls.Add(control);
            }
            if (useful) described["controls"] = controls;
            return described;
        }

        private void DialogAction(string saveAs, double seconds)
        {
            AutomationElement dialog = WaitDialog(null, seconds);
            Data[string.IsNullOrEmpty(saveAs) ? "dialog" : saveAs] = Describe(dialog, 0);
        }

        private void Dismiss(string buttonName, double seconds)
        {
            AutomationElement dialog = WaitDialog(null, seconds);
            Condition button = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button);
            AutomationElement target = null;
            foreach (AutomationElement item in dialog.FindAll(TreeScope.Children, button))
            {
                if (target == null && string.IsNullOrEmpty(buttonName)) target = item;
                if (!string.IsNullOrEmpty(buttonName) && SafeName(item) == buttonName) target = item;
            }
            if (target == null)
                throw new Refusal("control_missing", string.IsNullOrEmpty(buttonName)
                    ? "the dialog has no button" : "the dialog has no button '" + buttonName + "'");
            InvokeElement(target, "dialog button");
            if (!WaitClosed(dialog, 10))
                throw new Refusal("dialog_still_open", "the dialog did not close");
        }

        // Close whatever dialogs are open (a leftover message box or detail form
        // from an earlier run), innermost first; nothing open is not an error.
        private void ClearDialogs()
        {
            for (int round = 0; round < 6; round++)
            {
                List<AutomationElement> open = Dialogs();
                if (open.Count == 0) return;
                AutomationElement dialog = open[0];
                object window = Pattern(dialog, WindowPattern.Pattern);
                bool closed = false;
                try
                {
                    if (window != null)
                    {
                        ((WindowPattern)window).Close();
                        closed = WaitClosed(dialog, 5);
                    }
                    if (!closed)
                    {
                        Condition button = new PropertyCondition(
                            AutomationElement.ControlTypeProperty, ControlType.Button);
                        AutomationElement first = dialog.FindFirst(TreeScope.Children, button);
                        if (first != null)
                        {
                            InvokeElement(first, "dialog button");
                            closed = WaitClosed(dialog, 5);
                        }
                    }
                }
                catch (ElementNotAvailableException)
                {
                    closed = true;
                }
                if (!closed) throw new Refusal("dialog_still_open", "a dialog would not close");
            }
        }

        private void SaveAs(string path, double seconds)
        {
            if (string.IsNullOrEmpty(path)) throw new Refusal("path_missing", "save_as needs a path");
            Condition fileName = new PropertyCondition(AutomationElement.AutomationIdProperty, "1001");
            AutomationElement dialog = null;
            AutomationElement edit = null;
            DateTime deadline = DateTime.UtcNow.AddSeconds(seconds);
            while (edit == null)
            {
                foreach (AutomationElement candidate in Dialogs())
                {
                    AutomationElement found = candidate.FindFirst(TreeScope.Descendants, fileName);
                    if (found != null && found.Current.ControlType == ControlType.Edit)
                    {
                        dialog = candidate;
                        edit = found;
                        break;
                    }
                }
                if (edit == null)
                {
                    if (DateTime.UtcNow > deadline) throw new Refusal("dialog_missing", "no Save As dialog is open");
                    Thread.Sleep(200);
                }
            }
            ValuePattern value = Pattern(edit, ValuePattern.Pattern) as ValuePattern;
            if (value == null) throw new Refusal("pattern_unsupported", "the file name box takes no value");
            value.SetValue(path);
            Condition saveButton = new AndCondition(
                new PropertyCondition(AutomationElement.AutomationIdProperty, "1"),
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button));
            AutomationElement save = dialog.FindFirst(TreeScope.Children, saveButton)
                ?? dialog.FindFirst(TreeScope.Descendants, saveButton);
            if (save == null) throw new Refusal("control_missing", "the Save As dialog has no Save button");
            InvokeElement(save, "Save");
            if (!WaitClosed(dialog, 10))
                throw new Refusal("dialog_still_open", "the Save As dialog is still open (a name problem or a confirmation)");
        }

        // ---------------------------------------------------------------- look

        private static string TypeName(AutomationElement element)
        {
            string name = element.Current.ControlType.ProgrammaticName;
            return name.StartsWith("ControlType.", StringComparison.Ordinal) ? name.Substring(12) : name;
        }

        private static string Clip(string text)
        {
            return text.Length > MaxValueChars ? text.Substring(0, MaxValueChars) + "…" : text;
        }

        private static List<object> Controls(AutomationElement window, int budget)
        {
            List<object> controls = new List<object>();
            if (budget <= 0) budget = 40;
            Dictionary<string, AutomationElement> seen = new Dictionary<string, AutomationElement>();
            List<AutomationElement> ordered = new List<AutomationElement>();
            try
            {
                Collect(window, seen, ordered, 0);
            }
            catch (ElementNotAvailableException)
            {
            }
            foreach (AutomationElement element in ordered)
            {
                if (controls.Count >= budget) break;
                try
                {
                    ControlType type = element.Current.ControlType;
                    if (type == ControlType.Pane || type == ControlType.Group || type == ControlType.Header
                        || type == ControlType.HeaderItem || type == ControlType.ScrollBar) continue;
                    Dictionary<string, object> control = new Dictionary<string, object>();
                    control["id"] = element.Current.AutomationId;
                    control["type"] = TypeName(element);
                    control["name"] = element.Current.Name ?? "";
                    if (type == ControlType.DataGrid || type == ControlType.List || type == ControlType.Table)
                        control["value"] = Rows(element).Count + " rows";
                    else if (type != ControlType.Button && type != ControlType.Text)
                        control["value"] = Clip(ValueOf(element));
                    control["enabled"] = element.Current.IsEnabled;
                    controls.Add(control);
                }
                catch (ElementNotAvailableException)
                {
                }
            }
            return controls;
        }

        public Dictionary<string, object> Look()
        {
            Dictionary<string, object> look = new Dictionary<string, object>();
            AutomationElement window = Main();
            look["title"] = SafeName(window);
            look["controls"] = Controls(window, MaxControls);
            List<object> dialogs = new List<object>();
            int left = MaxControls - ((List<object>)look["controls"]).Count;
            foreach (AutomationElement dialog in Dialogs())
            {
                Dictionary<string, object> described = Describe(dialog, Math.Max(left, 1));
                object inner;
                if (described.TryGetValue("controls", out inner)) left -= ((List<object>)inner).Count;
                dialogs.Add(described);
            }
            look["dialogs"] = dialogs;
            return look;
        }

        // ---------------------------------------------------------------- JSON helpers

        public static string Str(Dictionary<string, object> action, string key)
        {
            object value;
            if (!action.TryGetValue(key, out value) || value == null) return null;
            return Convert.ToString(value, CultureInfo.InvariantCulture);
        }

        private static double Num(Dictionary<string, object> action, string key, double fallback)
        {
            object value;
            if (!action.TryGetValue(key, out value) || value == null) return fallback;
            try
            {
                return Convert.ToDouble(value, CultureInfo.InvariantCulture);
            }
            catch (FormatException)
            {
                return fallback;
            }
        }
    }

    internal static class Program
    {
        private static int Main()
        {
            JavaScriptSerializer json = new JavaScriptSerializer();
            json.MaxJsonLength = int.MaxValue;
            Dictionary<string, object> result = new Dictionary<string, object>();
            int step = -1;
            try
            {
                string input;
                using (StreamReader reader = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false)))
                    input = reader.ReadToEnd();
                Dictionary<string, object> request = json.DeserializeObject(input) as Dictionary<string, object>;
                if (request == null) throw new Refusal("request_invalid", "the request is not a JSON object");
                object pidValue;
                if (!request.TryGetValue("pid", out pidValue) || !(pidValue is int))
                    throw new Refusal("request_invalid", "the request needs an integer pid");
                Session session = new Session((int)pidValue, Session.Str(request, "window"));
                session.Main();
                object actions;
                if (request.TryGetValue("actions", out actions) && actions != null)
                {
                    IEnumerable list = actions as IEnumerable;
                    if (list == null || actions is string)
                        throw new Refusal("request_invalid", "actions must be a list");
                    step = 0;
                    foreach (object item in list)
                    {
                        Dictionary<string, object> action = item as Dictionary<string, object>;
                        if (action == null) throw new Refusal("request_invalid", "an action must be an object");
                        session.Run(action);
                        step++;
                    }
                    step = -1;
                }
                result["ok"] = true;
                result["data"] = session.Data;
                object look;
                if (!request.TryGetValue("look", out look) || !(look is bool) || (bool)look)
                    result["look"] = session.Look();
            }
            catch (Refusal refusal)
            {
                result.Clear();
                result["ok"] = false;
                result["code"] = refusal.Code;
                result["message"] = refusal.Message;
                result["step"] = step;
            }
            catch (ElementNotAvailableException error)
            {
                result.Clear();
                result["ok"] = false;
                result["code"] = "element_gone";
                result["message"] = error.Message;
                result["step"] = step;
            }
            catch (Exception error)
            {
                result.Clear();
                result["ok"] = false;
                result["code"] = "helper_error";
                result["message"] = error.GetType().Name + ": " + error.Message;
                result["step"] = step;
            }
            byte[] bytes = new UTF8Encoding(false).GetBytes(json.Serialize(result));
            using (Stream stdout = Console.OpenStandardOutput())
                stdout.Write(bytes, 0, bytes.Length);
            return 0;
        }
    }
}
