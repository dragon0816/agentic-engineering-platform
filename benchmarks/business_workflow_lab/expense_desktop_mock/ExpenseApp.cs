// Synthetic Expense desktop application, Windows Forms edition.
//
// Same data, rules, messages, fault modes and events as expense_app.py (the
// Tk edition), but every control is a native Win32/WinForms control with a
// stable Name (UIA AutomationId) and AccessibleName (UIA Name), so Windows UI
// Automation can see and operate all of it.
//
// Layout on disk (the exe lives in expense_desktop_mock/bin/):
//   ../export_xlsx.py                     helper that writes .xlsx with openpyxl
//   ../../operator/data/source.json       synthetic data
//   ../../operator/state/expense_fault.json   {"mode": "normal"|"export_fail_once", "fired": bool}
//   ../../operator/state/expense_events.jsonl operator evidence (JSON lines)
//
// Build: build.cmd (C# 5, .NET Framework 4.x csc.exe).

using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace ExpenseLab
{
    internal static class Lab
    {
        public static readonly string ExeDir = AppDomain.CurrentDomain.BaseDirectory;
        public static readonly string AppDir = Path.GetFullPath(Path.Combine(ExeDir, ".."));
        public static readonly string LabDir = Path.GetFullPath(Path.Combine(ExeDir, "..", ".."));
        public static readonly string DataFile = Path.Combine(LabDir, "operator", "data", "source.json");
        public static readonly string StateDir = Path.Combine(LabDir, "operator", "state");
        public static readonly string FaultFile = Path.Combine(StateDir, "expense_fault.json");
        public static readonly string EventsFile = Path.Combine(StateDir, "expense_events.jsonl");
        public static readonly string XlsxHelper = Path.Combine(AppDir, "export_xlsx.py");

        public const int PageSize = 8;
        public static readonly string[] Statuses = { "", "Draft", "Submitted", "Approved", "Rejected" };
        public static readonly string[] Columns = { "ExpenseID", "EmployeeID", "EmployeeName", "ProjectID",
            "ExpenseDate", "Category", "Currency", "Amount", "Status" };
        public static readonly int[] Widths = { 95, 80, 190, 75, 100, 85, 75, 100, 95 };
        public static readonly string[] ExportColumns = { "ExpenseID", "EmployeeID", "EmployeeName", "ProjectID",
            "ExpenseDate", "Category", "Currency", "Amount", "Status", "ReceiptID", "Description", "MissingReceipt" };
        public static readonly string[] DetailFields = { "ExpenseID", "EmployeeID", "EmployeeName", "ProjectID",
            "ExpenseDate", "Category", "Currency", "Amount", "Status", "ReceiptID", "Description", "MissingReceipt" };

        public static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        public static JavaScriptSerializer Serializer()
        {
            JavaScriptSerializer s = new JavaScriptSerializer();
            s.MaxJsonLength = int.MaxValue;
            return s;
        }

        // ---- JSON writing that matches Python's json.dumps(ensure_ascii=False) ----

        public static string JsonString(string text)
        {
            StringBuilder b = new StringBuilder("\"");
            foreach (char c in text)
            {
                switch (c)
                {
                    case '"': b.Append("\\\""); break;
                    case '\\': b.Append("\\\\"); break;
                    case '\n': b.Append("\\n"); break;
                    case '\r': b.Append("\\r"); break;
                    case '\t': b.Append("\\t"); break;
                    case '\b': b.Append("\\b"); break;
                    case '\f': b.Append("\\f"); break;
                    default:
                        if (c < 0x20) b.Append("\\u").Append(((int)c).ToString("x4"));
                        else b.Append(c);
                        break;
                }
            }
            return b.Append('"').ToString();
        }

        public static string JsonValue(object value)
        {
            if (value == null) return "null";
            if (value is string) return JsonString((string)value);
            if (value is bool) return (bool)value ? "true" : "false";
            if (value is int || value is long) return Convert.ToString(value, CultureInfo.InvariantCulture);
            if (value is IList<KeyValuePair<string, object>>) return JsonObject((IList<KeyValuePair<string, object>>)value);
            if (value is IDictionary<string, object>)
                return JsonObject(((IDictionary<string, object>)value).ToList());
            return JsonString(Convert.ToString(value, CultureInfo.InvariantCulture));
        }

        public static string JsonObject(IList<KeyValuePair<string, object>> pairs)
        {
            List<string> parts = new List<string>();
            foreach (KeyValuePair<string, object> pair in pairs)
                parts.Add(JsonString(pair.Key) + ": " + JsonValue(pair.Value));
            return "{" + string.Join(", ", parts) + "}";
        }

        public static KeyValuePair<string, object> P(string key, object value)
        {
            return new KeyValuePair<string, object>(key, value);
        }

        // ---- events and fault file ----

        public static void Event(string name, params KeyValuePair<string, object>[] detail)
        {
            try
            {
                Directory.CreateDirectory(StateDir);
                List<KeyValuePair<string, object>> line = new List<KeyValuePair<string, object>>();
                line.Add(P("at", DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss.fff", CultureInfo.InvariantCulture)));
                line.Add(P("event", name));
                line.AddRange(detail);
                File.AppendAllText(EventsFile, JsonObject(line) + "\n", Utf8NoBom);
            }
            catch (IOException)
            {
                // Evidence only; never break the app over the event log.
            }
        }

        public static bool ExportShouldFail()
        {
            Dictionary<string, object> state;
            try
            {
                state = Serializer().DeserializeObject(File.ReadAllText(FaultFile, Encoding.UTF8))
                    as Dictionary<string, object>;
            }
            catch (Exception)
            {
                return false;
            }
            if (state == null) return false;
            object mode;
            object fired;
            state.TryGetValue("mode", out mode);
            state.TryGetValue("fired", out fired);
            bool alreadyFired = fired is bool && (bool)fired;
            if ("export_fail_once".Equals(mode) && !alreadyFired)
            {
                state["fired"] = true;
                File.WriteAllText(FaultFile, JsonObject(state.ToList()), Utf8NoBom);
                return true;
            }
            return false;
        }

        public static bool ValidDate(string text)
        {
            DateTime parsed;
            return DateTime.TryParseExact(text, "yyyy-MM-dd", CultureInfo.InvariantCulture,
                DateTimeStyles.None, out parsed);
        }

        // Value as Python's str() would print it (bool -> True/False).
        public static string PyStr(object value)
        {
            if (value is bool) return (bool)value ? "True" : "False";
            return Convert.ToString(value, CultureInfo.InvariantCulture) ?? "";
        }

        public static string CsvField(string text)
        {
            if (text.IndexOfAny(new[] { ',', '"', '\r', '\n' }) >= 0)
                return "\"" + text.Replace("\"", "\"\"") + "\"";
            return text;
        }

        public static Font UiFont(float size)
        {
            return new Font("Microsoft JhengHei UI", size, FontStyle.Regular, GraphicsUnit.Point);
        }

        public static string Field(Dictionary<string, object> row, string key)
        {
            object value;
            row.TryGetValue(key, out value);
            return PyStr(value);
        }
    }

    internal sealed class MainForm : Form
    {
        private readonly List<Dictionary<string, object>> expenses = new List<Dictionary<string, object>>();
        private List<Dictionary<string, object>> rows = new List<Dictionary<string, object>>();
        private int page = 1;

        private ComboBox employee;
        private ComboBox project;
        private TextBox dateFrom;
        private TextBox dateTo;
        private ComboBox status;
        private Button queryButton;
        private ListView results;
        private Button previousButton;
        private Button nextButton;
        private TextBox countLabel;
        private Button detailsButton;
        private Button exportCsvButton;
        private Button exportExcelButton;

        public MainForm()
        {
            Dictionary<string, object> data = (Dictionary<string, object>)Lab.Serializer().DeserializeObject(
                File.ReadAllText(Lab.DataFile, Encoding.UTF8));
            foreach (object item in (IEnumerable)data["expenses"])
                expenses.Add((Dictionary<string, object>)item);
            List<string> employees = new List<string> { "" };
            foreach (object item in (IEnumerable)data["employees"])
                employees.Add((string)((Dictionary<string, object>)item)["EmployeeID"]);
            List<string> projects = new List<string> { "" };
            foreach (object item in (IEnumerable)data["projects"])
                projects.Add((string)((Dictionary<string, object>)item)["ProjectID"]);

            Text = "Expense Viewer (synthetic lab)";
            Name = "ExpenseViewer";
            AccessibleName = "Expense Viewer (synthetic lab)";
            Font = Lab.UiFont(9.75f);
            ClientSize = new Size(1080, 520);
            MinimumSize = new Size(900, 400);
            StartPosition = FormStartPosition.CenterScreen;
            KeyPreview = true;

            // Filters
            GroupBox filters = new GroupBox();
            filters.Text = "查詢條件 Filters";
            filters.Name = "FiltersGroup";
            filters.AccessibleName = "Filters";
            filters.Dock = DockStyle.Top;
            filters.Height = 64;
            filters.Padding = new Padding(8, 4, 8, 4);
            filters.TabIndex = 0;
            FlowLayoutPanel filterFlow = new FlowLayoutPanel();
            filterFlow.Dock = DockStyle.Fill;
            filterFlow.WrapContents = false;
            filterFlow.Name = "FilterPanel";
            filterFlow.AccessibleName = "FilterPanel";
            filterFlow.TabIndex = 0;
            filters.Controls.Add(filterFlow);

            int tab = 0;
            employee = Combo(filterFlow, "Employee 員工", "EmployeeFilter", employees, ref tab);
            project = Combo(filterFlow, "Project 專案", "ProjectFilter", projects, ref tab);
            dateFrom = Entry(filterFlow, "Date from 起 (YYYY-MM-DD)", "DateFrom", ref tab);
            dateTo = Entry(filterFlow, "Date to 迄 (YYYY-MM-DD)", "DateTo", ref tab);
            status = Combo(filterFlow, "Status 狀態", "StatusFilter", Lab.Statuses.ToList(), ref tab);
            queryButton = MakeButton("Query 查詢", "QueryButton", tab++);
            queryButton.Margin = new Padding(10, 3, 3, 3);
            queryButton.Click += delegate { Query(); };
            filterFlow.Controls.Add(queryButton);
            AcceptButton = queryButton;

            // Results
            results = new ListView();
            results.Name = "ResultsList";
            results.AccessibleName = "ResultsList";
            results.View = View.Details;
            results.FullRowSelect = true;
            results.MultiSelect = false;
            results.HideSelection = false;
            results.GridLines = true;
            results.Dock = DockStyle.Fill;
            results.TabIndex = 1;
            for (int i = 0; i < Lab.Columns.Length; i++)
            {
                ColumnHeader header = results.Columns.Add(Lab.Columns[i], Lab.Widths[i]);
                header.Name = Lab.Columns[i];
                if (Lab.Columns[i] == "Amount") header.TextAlign = HorizontalAlignment.Right;
            }
            results.MouseDoubleClick += delegate { Details(); };
            Panel tablePanel = new Panel();
            tablePanel.Dock = DockStyle.Fill;
            tablePanel.Padding = new Padding(8, 4, 8, 0);
            tablePanel.TabIndex = 1;
            tablePanel.Name = "ResultsPanel";
            tablePanel.AccessibleName = "ResultsPanel";
            tablePanel.Controls.Add(results);

            // Bottom bar: Previous / Next / count on the left, Details and exports on the right
            Panel bar = new Panel();
            bar.Dock = DockStyle.Bottom;
            bar.Height = 44;
            bar.Padding = new Padding(8, 4, 8, 4);
            bar.TabIndex = 2;
            bar.Name = "ButtonBar";
            bar.AccessibleName = "ButtonBar";
            FlowLayoutPanel left = new FlowLayoutPanel();
            left.Dock = DockStyle.Fill;
            left.WrapContents = false;
            left.TabIndex = 0;
            left.Name = "PagingPanel";
            left.AccessibleName = "PagingPanel";
            FlowLayoutPanel right = new FlowLayoutPanel();
            right.Dock = DockStyle.Right;
            right.AutoSize = true;
            right.WrapContents = false;
            right.TabIndex = 1;
            right.Name = "ActionPanel";
            right.AccessibleName = "ActionPanel";
            bar.Controls.Add(left);
            bar.Controls.Add(right);

            previousButton = MakeButton("◀ Previous 上一頁", "PreviousButton", 0);
            previousButton.Click += delegate { Turn(-1); };
            nextButton = MakeButton("Next 下一頁 ▶", "NextButton", 1);
            nextButton.Click += delegate { Turn(1); };
            // A borderless read-only TextBox rather than a Label: the UIA Name stays the
            // stable "CountLabel" while the visible text is readable through ValuePattern
            // (a Win32 static control exposes no Value, only its Name).
            countLabel = new TextBox();
            countLabel.Name = "CountLabel";
            countLabel.AccessibleName = "CountLabel";
            countLabel.ReadOnly = true;
            countLabel.TabStop = false;
            countLabel.BorderStyle = BorderStyle.None;
            countLabel.BackColor = SystemColors.Control;
            countLabel.Width = 260;
            countLabel.Margin = new Padding(12, 9, 3, 3);
            countLabel.Text = "Total 0 rows · Page 0 / 0";
            left.Controls.Add(previousButton);
            left.Controls.Add(nextButton);
            left.Controls.Add(countLabel);

            detailsButton = MakeButton("Details 明細", "DetailsButton", 0);
            detailsButton.Click += delegate { Details(); };
            exportCsvButton = MakeButton("Export CSV 匯出 CSV", "ExportCsvButton", 1);
            exportCsvButton.Click += delegate { Export("csv"); };
            exportExcelButton = MakeButton("Export Excel 匯出 Excel", "ExportExcelButton", 2);
            exportExcelButton.Click += delegate { Export("xlsx"); };
            right.Controls.Add(detailsButton);
            right.Controls.Add(exportCsvButton);
            right.Controls.Add(exportExcelButton);

            Label statusBar = new Label();
            statusBar.Name = "StatusBar";
            statusBar.AccessibleName = "StatusBar";
            statusBar.Text = "Ready";
            statusBar.BorderStyle = BorderStyle.Fixed3D;
            statusBar.Dock = DockStyle.Bottom;
            statusBar.Height = 22;
            statusBar.TextAlign = ContentAlignment.MiddleLeft;

            // Dock order: the last control added is docked first.
            Controls.Add(tablePanel);
            Controls.Add(bar);
            Controls.Add(statusBar);
            Controls.Add(filters);

            Shown += delegate { employee.Focus(); };
            Render();
            Lab.Event("app_started");
        }

        private static Label MakeLabel(string text, string name)
        {
            Label label = new Label();
            label.Text = text;
            label.Name = name;
            label.AutoSize = true;
            label.Margin = new Padding(8, 8, 2, 3);
            return label;
        }

        private static Button MakeButton(string text, string name, int tabIndex)
        {
            Button button = new Button();
            button.Text = text;
            button.Name = name;
            button.AccessibleName = name;
            button.AutoSize = true;
            button.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            button.Padding = new Padding(6, 2, 6, 2);
            button.TabIndex = tabIndex;
            button.UseVisualStyleBackColor = true;
            return button;
        }

        private static ComboBox Combo(FlowLayoutPanel parent, string label, string name, List<string> values, ref int tab)
        {
            Label caption = MakeLabel(label, name + "Label");
            caption.TabIndex = tab++;
            parent.Controls.Add(caption);
            ComboBox combo = new ComboBox();
            combo.Name = name;
            combo.AccessibleName = name;
            combo.DropDownStyle = ComboBoxStyle.DropDownList;
            combo.Width = 92;
            combo.TabIndex = tab++;
            combo.Margin = new Padding(0, 4, 3, 3);
            foreach (string value in values) combo.Items.Add(value);
            combo.SelectedIndex = 0;
            parent.Controls.Add(combo);
            return combo;
        }

        private static TextBox Entry(FlowLayoutPanel parent, string label, string name, ref int tab)
        {
            Label caption = MakeLabel(label, name + "Label");
            caption.TabIndex = tab++;
            parent.Controls.Add(caption);
            TextBox box = new TextBox();
            box.Name = name;
            box.AccessibleName = name;
            box.Width = 100;
            box.TabIndex = tab++;
            box.Margin = new Padding(0, 4, 3, 3);
            parent.Controls.Add(box);
            return box;
        }

        private static string Selected(ComboBox combo)
        {
            return combo.SelectedItem == null ? "" : (string)combo.SelectedItem;
        }

        private List<KeyValuePair<string, object>> Filters()
        {
            return new List<KeyValuePair<string, object>>
            {
                Lab.P("employee", Selected(employee)),
                Lab.P("project", Selected(project)),
                Lab.P("from", dateFrom.Text.Trim()),
                Lab.P("to", dateTo.Text.Trim()),
                Lab.P("status", Selected(status)),
            };
        }

        private static string Get(List<KeyValuePair<string, object>> chosen, string key)
        {
            return (string)chosen.First(p => p.Key == key).Value;
        }

        private void Query()
        {
            List<KeyValuePair<string, object>> chosen = Filters();
            foreach (string key in new[] { "from", "to" })
            {
                string value = Get(chosen, key);
                if (value.Length > 0 && !Lab.ValidDate(value))
                {
                    MessageBox.Show(this, "日期格式錯誤：" + value + "（需為 YYYY-MM-DD）", "查詢錯誤 Query error",
                        MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }
            }
            string emp = Get(chosen, "employee");
            string proj = Get(chosen, "project");
            string stat = Get(chosen, "status");
            string from = Get(chosen, "from");
            string to = Get(chosen, "to");
            rows = expenses.Where(e =>
                    (emp.Length == 0 || Lab.Field(e, "EmployeeID") == emp)
                    && (proj.Length == 0 || Lab.Field(e, "ProjectID") == proj)
                    && (stat.Length == 0 || Lab.Field(e, "Status") == stat)
                    && (from.Length == 0 || string.CompareOrdinal(Lab.Field(e, "ExpenseDate"), from) >= 0)
                    && (to.Length == 0 || string.CompareOrdinal(Lab.Field(e, "ExpenseDate"), to) <= 0))
                .OrderBy(e => Lab.Field(e, "ExpenseDate"), StringComparer.Ordinal)
                .ThenBy(e => Lab.Field(e, "ExpenseID"), StringComparer.Ordinal)
                .ToList();
            page = 1;
            Render();
            Lab.Event("query", Lab.P("filters", chosen), Lab.P("total", rows.Count));
            if (rows.Count > 0)
                MessageBox.Show(this, "查詢完成，共 " + rows.Count + " 筆。", "查詢完成 Query complete",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            else
                MessageBox.Show(this, "查無符合條件的資料（0 筆）。", "查無資料 No results",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private int Pages()
        {
            return Math.Max(1, (rows.Count + Lab.PageSize - 1) / Lab.PageSize);
        }

        private void Turn(int step)
        {
            page = Math.Min(Math.Max(1, page + step), Pages());
            Render();
            Lab.Event("page", Lab.P("page", page));
        }

        private void Render()
        {
            results.BeginUpdate();
            results.Items.Clear();
            int start = (page - 1) * Lab.PageSize;
            foreach (Dictionary<string, object> row in rows.Skip(start).Take(Lab.PageSize))
            {
                ListViewItem item = new ListViewItem(Lab.Field(row, Lab.Columns[0]));
                item.Name = Lab.Field(row, "ExpenseID");
                for (int i = 1; i < Lab.Columns.Length; i++) item.SubItems.Add(Lab.Field(row, Lab.Columns[i]));
                results.Items.Add(item);
            }
            results.EndUpdate();
            int pages = rows.Count > 0 ? Pages() : 0;
            countLabel.Text = "Total " + rows.Count + " rows · Page " + (rows.Count > 0 ? page : 0) + " / " + pages;
            previousButton.Enabled = page > 1;
            nextButton.Enabled = page < Pages();
        }

        private void Details()
        {
            if (results.SelectedItems.Count == 0)
            {
                MessageBox.Show(this, "請先選取一筆費用。", "未選取 No selection",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            string id = results.SelectedItems[0].Text;
            Dictionary<string, object> row = expenses.First(e => Lab.Field(e, "ExpenseID") == id);
            Lab.Event("detail", Lab.P("id", id));
            using (DetailForm dialog = new DetailForm(row))
            {
                dialog.ShowDialog(this);
            }
        }

        private void Export(string kind)
        {
            if (rows.Count == 0)
            {
                DialogResult answer = MessageBox.Show(this, "目前結果為 0 筆，仍要匯出只有表頭的檔案嗎？", "匯出 Export",
                    MessageBoxButtons.YesNo, MessageBoxIcon.Question);
                if (answer != DialogResult.Yes) return;
            }
            string extension = kind == "csv" ? ".csv" : ".xlsx";
            string path;
            using (SaveFileDialog save = new SaveFileDialog())
            {
                save.Title = "Save As 另存新檔";
                save.FileName = "expenses_export" + extension;
                save.DefaultExt = extension.Substring(1);
                save.AddExtension = true;
                save.Filter = kind == "csv" ? "CSV (*.csv)|*.csv" : "Excel workbook (*.xlsx)|*.xlsx";
                if (save.ShowDialog(this) != DialogResult.OK || save.FileName.Length == 0)
                {
                    Lab.Event("export_cancelled", Lab.P("kind", kind));
                    return;
                }
                path = save.FileName;
            }
            if (Lab.ExportShouldFail())
            {
                Lab.Event("export_failed_injected", Lab.P("kind", kind), Lab.P("path", path));
                MessageBox.Show(this, "暫時無法寫入，請重試。 (Temporary write failure, retry)", "匯出失敗 Export failed",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            string error = kind == "csv" ? WriteCsv(path) : WriteXlsx(path);
            if (error != null)
            {
                Lab.Event("export_failed", Lab.P("kind", kind), Lab.P("path", path), Lab.P("error", error));
                MessageBox.Show(this, "無法寫入檔案：" + error, "匯出失敗 Export failed",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            Lab.Event("export", Lab.P("kind", kind), Lab.P("path", path), Lab.P("rows", rows.Count));
            MessageBox.Show(this, "已匯出 " + rows.Count + " 筆至\n" + path, "匯出完成 Export complete",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        // UTF-8 with BOM, CRLF line ends, minimal quoting (like Python's csv module).
        private string WriteCsv(string path)
        {
            try
            {
                StringBuilder text = new StringBuilder();
                text.Append(string.Join(",", Lab.ExportColumns.Select(Lab.CsvField))).Append("\r\n");
                foreach (Dictionary<string, object> row in rows)
                    text.Append(string.Join(",", Lab.ExportColumns.Select(c => Lab.CsvField(Lab.Field(row, c)))))
                        .Append("\r\n");
                File.WriteAllText(path, text.ToString(), new UTF8Encoding(true));
                return null;
            }
            catch (Exception e)
            {
                if (e is IOException || e is UnauthorizedAccessException || e is ArgumentException
                    || e is NotSupportedException || e is System.Security.SecurityException)
                    return e.Message;
                throw;
            }
        }

        // Delegates to export_xlsx.py (system python + openpyxl) through a temporary JSON file.
        private string WriteXlsx(string path)
        {
            string request = Path.Combine(Path.GetTempPath(), "expense_export_" + Guid.NewGuid().ToString("N") + ".json");
            try
            {
                List<object> body = new List<object>();
                foreach (Dictionary<string, object> row in rows)
                {
                    List<object> values = new List<object>();
                    foreach (string column in Lab.ExportColumns)
                    {
                        object value;
                        row.TryGetValue(column, out value);
                        values.Add(value);
                    }
                    body.Add(values);
                }
                Dictionary<string, object> payload = new Dictionary<string, object>();
                payload["path"] = path;
                payload["columns"] = Lab.ExportColumns;
                payload["rows"] = body;
                File.WriteAllText(request, Lab.Serializer().Serialize(payload), Lab.Utf8NoBom);

                ProcessStartInfo info = new ProcessStartInfo("python");
                info.Arguments = "\"" + Lab.XlsxHelper + "\" \"" + request + "\"";
                info.UseShellExecute = false;
                info.CreateNoWindow = true;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                info.StandardErrorEncoding = Encoding.UTF8;
                info.StandardOutputEncoding = Encoding.UTF8;
                info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                using (Process process = Process.Start(info))
                {
                    string stderr = process.StandardError.ReadToEnd();
                    process.StandardOutput.ReadToEnd();
                    if (!process.WaitForExit(120000))
                    {
                        try { process.Kill(); } catch (InvalidOperationException) { }
                        return "Excel helper timed out";
                    }
                    if (process.ExitCode != 0)
                    {
                        string[] lines = stderr.Trim().Split('\n');
                        string last = lines.Length > 0 ? lines[lines.Length - 1].Trim() : "";
                        return last.Length > 0 ? last : "Excel helper exited with code " + process.ExitCode;
                    }
                }
                return null;
            }
            catch (System.ComponentModel.Win32Exception e)
            {
                return "python not available: " + e.Message;
            }
            catch (IOException e)
            {
                return e.Message;
            }
            finally
            {
                try { File.Delete(request); } catch (IOException) { } catch (UnauthorizedAccessException) { }
            }
        }
    }

    internal sealed class DetailForm : Form
    {
        public DetailForm(Dictionary<string, object> row)
        {
            string id = Lab.Field(row, "ExpenseID");
            Text = "Expense detail " + id;
            Name = "ExpenseDetail";
            AccessibleName = "Expense detail " + id;
            Font = Lab.UiFont(9.75f);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent;
            AutoSize = true;
            AutoSizeMode = AutoSizeMode.GrowAndShrink;
            Padding = new Padding(10);

            TableLayoutPanel grid = new TableLayoutPanel();
            grid.Name = "DetailGrid";
            grid.AccessibleName = "DetailGrid";
            grid.ColumnCount = 2;
            grid.AutoSize = true;
            grid.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            grid.Dock = DockStyle.Fill;
            grid.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            grid.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

            int tab = 0;
            foreach (string field in Lab.DetailFields)
            {
                Label caption = new Label();
                caption.Text = field + ":";
                caption.Name = "Detail" + field + "Label";
                caption.AutoSize = true;
                caption.Anchor = field == "Description" ? AnchorStyles.Top | AnchorStyles.Right : AnchorStyles.Right;
                caption.Margin = new Padding(4, 5, 4, 2);
                caption.TabIndex = tab++;
                TextBox value = new TextBox();
                value.Name = "Detail" + field;
                value.AccessibleName = "Detail" + field;
                value.ReadOnly = true;
                value.Width = 360;
                value.TabIndex = tab++;
                value.Margin = new Padding(0, 2, 0, 2);
                if (field == "MissingReceipt")
                {
                    value.Text = Lab.Field(row, field).ToLowerInvariant();
                }
                else if (field == "Description")
                {
                    value.Multiline = true;
                    value.ScrollBars = ScrollBars.Vertical;
                    value.WordWrap = true;
                    value.Height = 80;
                    // Normalise to CRLF so the TextBox shows the line break.
                    value.Text = Lab.Field(row, field).Replace("\r\n", "\n").Replace("\n", "\r\n");
                }
                else
                {
                    value.Text = Lab.Field(row, field);
                }
                grid.Controls.Add(caption);
                grid.Controls.Add(value);
            }

            Button close = new Button();
            close.Text = "Close 返回";
            close.Name = "CloseButton";
            close.AccessibleName = "CloseButton";
            close.AutoSize = true;
            close.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            close.Padding = new Padding(6, 2, 6, 2);
            close.Anchor = AnchorStyles.Right;
            close.Margin = new Padding(0, 8, 0, 0);
            close.TabIndex = tab;
            close.DialogResult = DialogResult.Cancel;
            close.UseVisualStyleBackColor = true;
            grid.Controls.Add(new Label { AutoSize = true, Name = "DetailSpacer" });
            grid.Controls.Add(close);
            Controls.Add(grid);

            AcceptButton = close;
            CancelButton = close;
            Shown += delegate { close.Focus(); };
        }
    }

    internal static class Program
    {
        [STAThread]
        private static int Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
            return 0;
        }
    }
}
