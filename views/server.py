"""Data sources > College server: connect read-only to the college ERP and Moodle databases and sync."""
import json
import os
import subprocess
import sys

import pandas as pd
import streamlit as st

from src import config as C
from src import connector as cn
from src import demo_server
from src import ui


def server_form(prefix, saved, label):
    """Connection fields for one server. Returns the config dict and the password typed this session."""
    names = list(cn.DIALECTS)
    dialect = st.selectbox("Database type", names, key=f"{prefix}_dialect",
                           index=names.index(saved.get("dialect", "MySQL / MariaDB"))
                           if saved.get("dialect") in names else 0)
    if dialect == "SQLite file":
        path = st.text_input("Database file", value=saved.get("database", ""), key=f"{prefix}_file")
        return dict(dialect=dialect, database=path), ""
    c = st.columns([2, 1])
    host = c[0].text_input("Server address", value=saved.get("host", ""), key=f"{prefix}_host",
                           placeholder="e.g. 10.0.4.12 or erp.college.edu.in")
    port = c[1].number_input("Port", value=int(saved.get("port") or cn.DIALECTS[dialect][1]), step=1,
                             key=f"{prefix}_port")
    db = st.text_input("Database name", value=saved.get("database", ""), key=f"{prefix}_db",
                       placeholder="e.g. college_erp" if prefix == "erp" else "e.g. moodle")
    c = st.columns(2)
    user = c[0].text_input("Read-only username", value=saved.get("username", ""), key=f"{prefix}_user")
    pw = c[1].text_input("Password", type="password", key=f"{prefix}_pw",
                         help="Used for this session only. EarlySignal never saves passwords.")
    return dict(dialect=dialect, host=host.strip(), port=int(port), database=db.strip(), username=user.strip()), pw


def render(meta):
    conn = cn.load_conn()
    st.markdown("""<div class='flow'>
<div><div class='h'><span>1</span>Connect read-only</div><div class='d'>The college's IT team creates a <b>read-only
login</b> on the ERP database (and on Moodle, if used). EarlySignal can look, never change.</div></div>
<div><div class='h'><span>2</span>Map once</div><div class='d'>A few <b>SELECT queries</b> tell EarlySignal where
students, marks and attendance live. Defaults fit common ERPs; IT adjusts table names once.</div></div>
<div><div class='h'><span>3</span>Sync every night</div><div class='d'>New attendance, marks and LMS activity flow in
<b>automatically</b> and every page rebuilds. No more spreadsheets.</div></div></div>""", unsafe_allow_html=True)

    # 1. connect ------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 1. Connect")
        modes = ["Demo college server", "My college's server"]
        mode = st.radio("Server", modes, horizontal=True, key="srv_mode", label_visibility="collapsed",
                        index=1 if conn.get("mode") == "server" else 0)
        passwords = {}
        if mode == modes[0]:
            st.markdown("<div class='muted'>A demo college ERP and a Moodle LMS, laid out the way colleges really "
                        "store data: attendance is one row per student per class hour, Moodle uses its own table "
                        "names. Built from the sample college, so you can try every step.</div>",
                        unsafe_allow_html=True)
            if not demo_server.exists():
                if st.button("Start the demo server", icon=":material/dns:", type="primary"):
                    rc, _ = run_job([sys.executable, "-m", "src.demo_server"],
                                    "Creating the demo ERP and Moodle databases (about 15 seconds)...")
                    if rc == 0 and demo_server.exists():
                        demo_server_tables.clear()
                        st.rerun()
                cfgs = {}
            else:
                cfgs = cn.demo_cfgs()
                T = demo_server_tables()
                c = st.columns(3)
                c[0].markdown(ui.kpi("🗄️", "#e6effc", ui.BLUE, "ERP database", f"{(T['Database'] == 'ERP').sum()}",
                                     " tables", "students, marks, attendance"), unsafe_allow_html=True)
                att = int(T.loc[T["Table"] == "attendance", "Rows"].sum())
                c[1].markdown(ui.kpi("🕘", "#efe8fc", ui.PURPLE, "Attendance rows", f"{att:,}", "",
                                     "one per student per class hour"), unsafe_allow_html=True)
                c[2].markdown(ui.kpi("💻", "#e5f6ec", ui.GREEN, "Moodle database", f"{(T['Database'] == 'Moodle').sum()}",
                                     " tables", "logins and assignments"), unsafe_allow_html=True)
                with st.expander("See the tables on the demo server"):
                    st.dataframe(T, hide_index=True, height=320)
        else:
            a, b = st.columns(2, gap="large")
            with a:
                st.markdown("**College ERP database** (needed)")
                erp, pw_erp = server_form("erp", conn.get("erp", {}), "ERP")
            with b:
                use_lms = st.toggle("We use Moodle (optional)", value=bool(conn.get("lms")), key="use_lms")
                lms, pw_lms = server_form("lms", conn.get("lms", {}), "Moodle") if use_lms else (None, "")
            passwords = {"erp": pw_erp or os.environ.get("EARLYSIGNAL_ERP_PASSWORD", ""),
                         "lms": pw_lms or os.environ.get("EARLYSIGNAL_LMS_PASSWORD", "")}
            cfgs = {"erp": erp} | ({"lms": lms} if lms else {})
            if st.button("Test connection", icon=":material/lan:"):
                for k, cfg in cfgs.items():
                    ok, msg, tables = cn.test(cfg, passwords.get(k, ""))
                    (st.success if ok else st.error)(f"{'ERP' if k == 'erp' else 'Moodle'}: {msg}")
                    if ok and tables:
                        st.caption(", ".join(tables[:40]) + (" ..." if len(tables) > 40 else ""))
                cn.save_conn(dict(conn, mode="server", erp=erp, lms=lms))
            st.caption("EarlySignal must be able to reach the server: run it inside the campus network or over the "
                       "college VPN. Ask IT for a login that can only SELECT. Supported: MySQL / MariaDB, "
                       "PostgreSQL, SQL Server, Oracle.")

    # 2. map ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 2. Map your tables")
        st.markdown("<div class='muted'>EarlySignal reads with these SELECT queries. They match the demo server and a "
                    "typical ERP; for a real college the IT team changes table and column names once. Anything that "
                    "is not a single SELECT is refused.</div>", unsafe_allow_html=True)
        queries = dict(conn.get("queries") or {})
        last = st.session_state.get("srv_report", {})
        rows = []
        for slot, (server, sheet, need, label, _) in cn.SLOTS.items():
            r = last.get(slot)
            rows.append({"What it reads": label, "From": "ERP" if server == "erp" else "Moodle",
                         "Needed?": "Needed" if need else "Optional",
                         "Query": "Edited" if slot in queries else "Default",
                         "Last run": "-" if r is None else (f"Error: {r['error'][:60]}" if r["error"]
                                                            else f"{r['rows']:,} rows in {r['secs']} s")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, height=300)
        slots = list(cn.SLOTS)
        pick = st.selectbox("See or edit a query", slots, format_func=lambda s: cn.SLOTS[s][3], key="srv_pick")
        sql = st.text_area("SQL", value=queries.get(pick, cn.DEFAULT_SQL[pick]), height=190, key=f"sql_{pick}",
                           label_visibility="collapsed")
        c = st.columns([1, 1, 3])
        if c[0].button("Save query", icon=":material/save:", use_container_width=True):
            try:
                cn.check_sql(sql)
                if sql.strip() == cn.DEFAULT_SQL[pick]:
                    queries.pop(pick, None)
                else:
                    queries[pick] = sql.strip()
                cn.save_conn(dict(conn, queries=queries))
                st.success("Saved.")
            except ValueError as e:
                st.error(str(e))
        if c[1].button("Reset to default", use_container_width=True, disabled=pick not in queries):
            queries.pop(pick, None)
            cn.save_conn(dict(conn, queries=queries))
            st.session_state.pop(f"sql_{pick}", None)
            st.rerun()

    # 3. sync ---------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 3. Sync and build")
        demo = mode == modes[0]
        c = st.columns([1.6, 1.3, 1.2], vertical_alignment="bottom")
        name = c[0].text_input("College name", key="srv_name",
                               value=conn.get("college_name") or ("Demo College" if demo else ""))
        go = c[1].button("Sync now and build", type="primary", icon=":material/sync:", use_container_width=True,
                         disabled=not cfgs or not (cfgs.get("erp") or {}).get("database"))
        reset = c[2].button("Switch back to the sample college", use_container_width=True,
                            disabled=meta.get("using_sample", True), key="reset_srv")
        st.caption("Reads the latest data, checks it, and rebuilds every page in about a minute. If anything fails, "
                   "the dashboard keeps the previous data.")
        if go:
            from views.upload import finish, show_checks
            cn.save_conn(dict(conn, mode="demo" if demo else "server", college_name=name.strip() or "My College",
                              **({} if demo else {"erp": cfgs.get("erp"), "lms": cfgs.get("lms")})))
            out_json = C.ROOT / "data" / "last_sync.json"
            out_json.unlink(missing_ok=True)
            env = {"EARLYSIGNAL_ERP_PASSWORD": passwords.get("erp", ""),
                   "EARLYSIGNAL_LMS_PASSWORD": passwords.get("lms", "")}
            rc, _ = run_job([sys.executable, "-m", "src.sync", "--json", str(out_json)] + (["--demo"] if demo else []),
                            "Syncing from the college server (read-only)...", env)
            try:
                out = json.loads(out_json.read_text())
            except Exception:
                out = None
            if out is None:
                st.error("The sync stopped before it finished. " + KILLED_HINT if rc and rc < 0 else
                         "The sync stopped before it finished. The dashboard still shows the previous data.")
            else:
                st.session_state["srv_report"] = {r["slot"]: r for r in out["report"]}
                R = pd.DataFrame([{"What it reads": r["label"], "Rows": "-" if r["rows"] is None else f"{r['rows']:,}",
                                   "Seconds": r["secs"], "Problem": r["error"] or ""} for r in out["report"]])
                st.dataframe(R, hide_index=True, height=260)
                for n in out["notes"]:
                    st.caption(n)
                for e in out["errors"]:
                    st.error(e)
                if out["checks"]:
                    show_checks(out)
                if out.get("built"):
                    finish()
                    st.success("Done. Every page now uses the data from the college server.")
                    st.page_link(ui.PAGES["dashboard"], label="Open the dashboard", icon=":material/dashboard:")
                elif out["ok"]:
                    st.error("The data was read and checked, but the rebuild did not finish, so the previous data is "
                             "kept. " + (KILLED_HINT if rc and rc < 0 else ""))
                    if out.get("log"):
                        st.code(out["log"])
                elif out["checks"]:
                    st.error("The data was read, but some checks failed (marked ❌). Adjust the queries in step 2.")
        if reset:
            from views.upload import reset_to_sample
            reset_to_sample()

    with st.expander("Automatic nightly sync"):
        st.markdown("Run EarlySignal on a computer **inside the campus network** (or connected over the college VPN), "
                    "connect once on this page, then add one line to the scheduler. Every night it reads the new "
                    "attendance, marks and Moodle activity and rebuilds every page. If the server is down, the "
                    "previous day's data stays.")
        st.markdown("**Linux (cron):**")
        st.code(f"0 2 * * *  cd {C.ROOT} && EARLYSIGNAL_ERP_PASSWORD='...' EARLYSIGNAL_LMS_PASSWORD='...' "
                "python -m src.sync >> sync.log 2>&1", language="bash")
        st.markdown("**Windows (Task Scheduler):** run `python -m src.sync` in this folder every night, with the "
                    "two passwords set as environment variables. To try it on the demo server: `python -m src.sync --demo`.")
    with st.expander("How colleges store this data, and how EarlySignal reaches it"):
        st.markdown("""
| Data | Where it usually lives | How EarlySignal reads it |
|---|---|---|
| Students, attendance, internal marks, results | College ERP database (MySQL, PostgreSQL, SQL Server or Oracle) on a campus server or the vendor's cloud | Read-only SQL login (or the vendor's report API) |
| Online activity, assignments | Moodle database (MySQL or PostgreSQL) | Read-only SQL login on Moodle's own tables |
| University exam results | Excel / PDF from the university portal, often imported into the ERP | From the ERP once imported, or the Excel upload |
| Placement training, events, feedback | Excel sheets and Google Forms kept by each office | The Excel upload tab, until they move into the ERP |

**What the college needs to provide:** a read-only database login, network access from the EarlySignal machine
(same campus network or VPN), and approval under its data policy. Under India's Digital Personal Data Protection
Act, 2023 the college stays responsible for its students' data, so EarlySignal reads only the columns it needs,
never writes, never stores passwords, and keeps the data on the college's own machine.

**If the ERP is a vendor's cloud product** without database access, use the vendor's scheduled report export
(saved nightly to a shared folder) with the Excel tab, or ask the vendor for an API.
""")


KILLED_HINT = ("The system stopped it, most likely because the workspace ran out of memory. Close other apps or "
               "browser tabs in the workspace and try again.")


def run_job(cmd, label, env=None):
    """Run a heavy job in its own process (so the app itself stays light) and show its progress live."""
    full_env = dict(os.environ, PYTHONUNBUFFERED="1", **(env or {}))
    lines = []
    with st.status(label, expanded=True) as box:
        proc = subprocess.Popen(cmd, cwd=str(C.ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env=full_env)
        for line in proc.stdout:
            line = line.rstrip()
            if line and not line.startswith(("Traceback", "  File", "    ")):
                lines.append(line)
                box.write(line)
        rc = proc.wait()
        if rc == 0:
            box.update(label=label.replace("...", ": done"), state="complete", expanded=False)
        else:
            box.update(label=label.replace("...", ": stopped"), state="error", expanded=True)
            if rc < 0:
                st.error(KILLED_HINT)
    return rc, lines


@st.cache_data(show_spinner=False)
def demo_server_tables():
    t = demo_server.tables()
    return pd.DataFrame([{"Database": db, "Table": tb, "Rows": n} for (db, tb), n in t.items()])
