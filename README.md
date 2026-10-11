# EarlySignal: Student Success Intelligence

**KPMG Smart Campus Analytics challenge.** Most dashboards show which students are struggling.
EarlySignal shows which students **will** struggle, weeks before marks drop, **why**, the **smallest
action** that changes it, and **whether that action worked**.

---

## Run it on Nimbus (about 5 minutes)

1. **Open your Python workspace** in Nimbus (the one where the Streamlit test worked).
2. **Upload the project.** Drag the unzipped `earlysignal` folder (or `earlysignal.zip`) into the file list on the
   left of VS Code.
3. **Open a terminal** (menu → Terminal → New Terminal) and run these lines one at a time
   (if you uploaded the zip, first run `unzip earlysignal.zip`):

   ```bash
   cd earlysignal
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. **Open the app** the same way you opened the test page: the proxy link ending in `/proxy/8501/`.
   The first load takes about 15 seconds while it builds the scores. After that it is instant.
5. **Sign in** with `admin@college.edu.in` and password `admin123` (whole college), or
   `hod.cse@college.edu.in` / `hod123` to see the app as the CSE head of department.
   These are demo sign-ins, not real security. Refreshing the browser signs you out.

To stop the app press `Ctrl + C` in the terminal. To start it again: `streamlit run app.py`.

**Optional AI features.** Get a free key at aistudio.google.com, then paste it into
*AI assistant key (optional)* at the bottom of the app's menu. Without a key, everything still works and uses built-in
template text. Only anonymised numbers are ever sent to the AI.

**Rebuild everything from scratch** (new data, retrained models): `python -m src.generate_data` then
`python -m src.pipeline`.

---

## What's inside

A sign-in page, then eleven pages in the left menu. Every list of students has a **View** button that opens that
student's profile.

| Page | What it shows | Brief criteria |
|---|---|---|
| Dashboard | Greeting, 4 summary cards, Student Success trend, risk distribution, students needing attention, this week's priorities | Dashboard, trends, insights |
| Students | Searchable directory with department, year and risk filters | Unified student view |
| Student profile | Score ring, and 9 tabs: Overview, Academic, Attendance, LMS, Engagement, Placement, Skills, Feedback, Action plan | Explainable score (bonus) |
| Analytics | Attendance, engagement and placement trends, risk factors, and proof that the early warning works | Key trends, risk identification |
| Segments | 7 student groups as cards, each with a plan you can assign to the whole group | Segmentation (bonus) |
| Placement | Who isn't job-ready, and what gets students placed here | Placement risk |
| Interventions | Suggested actions, follow-ups, what works, and a downloadable weekly report | Decision intelligence |
| AI assistant | Plain-English questions, e.g. "final years with CGPA above 8 and no mock interviews" | AI |
| Data sources | Connect read-only to the college's ERP and Moodle servers with nightly sync, or upload one Excel file | Real-world use |
| Data quality | How 12 messy files became one record per student | Data integration (30%) |
| Fairness | Do flags fall unfairly on any group? | Problem understanding |
| How it works | What the Success Score and risk level mean | Score note |

## Using a college's own data

### Option 1: connect to the college's servers (automatic)

How colleges actually store this data:

| Data | Where it usually lives |
|---|---|
| Students, attendance, internal marks, results | The college ERP: a MySQL, PostgreSQL, SQL Server or Oracle database on a campus server or the vendor's cloud. Attendance is stored per class hour (one row per student per period, P / A / OD). |
| Online activity, assignments | Moodle's own database (MySQL or PostgreSQL): `mdl_user`, `mdl_logstore_standard_log`, `mdl_assign`, `mdl_assign_submission` |
| University results | Excel / PDF from the university portal, usually imported into the ERP |
| Placement training, events, feedback | Excel sheets and Google Forms kept by each office |

**Data sources → College server** connects to these databases **read-only**:

1. **Connect.** The college's IT team creates a read-only login. Enter the server address, database and login
   (MySQL / MariaDB, PostgreSQL, SQL Server or Oracle). Press **Test connection**.
2. **Map once.** 14 short SELECT queries tell EarlySignal where students, marks, attendance and Moodle activity
   live. The defaults fit the demo server and a typical ERP; IT edits table names once. Anything that is not a
   single SELECT is refused, and on PostgreSQL / MySQL the session itself is opened read-only.
3. **Sync now and build.** Period-wise attendance and Moodle timestamps are turned into semester and week using the
   academic calendar, then checked and scored exactly like an upload. For nightly sync, run on a machine inside the
   campus network:
   `0 2 * * * cd /opt/earlysignal && EARLYSIGNAL_ERP_PASSWORD=... python -m src.sync`
   Passwords are never saved by EarlySignal.

**Try it without a college:** choose **Demo college server** and press **Sync now and build**. The demo server is an
ERP database (14 tables, 855,290 period-wise attendance rows) and a Moodle database built from the sample college
(`python -m src.demo_server`, about 15 s, created on first use). Synced through the server path, every student gets
exactly the same scores as the sample college, which shows nothing is lost on the way.

Also tested against a real PostgreSQL 16 server over TCP with a read-only user: connected, synced 855,290
attendance rows in about 10 s, and an attempted UPDATE was refused by the database.

Other drivers: `pip install -r requirements-server.txt` (PostgreSQL, SQL Server, Oracle). MySQL works out of the box.

If the ERP is a vendor's cloud product without database access, use its scheduled report export with option 2, or ask
the vendor for an API.

### Option 2: upload one Excel file (manual)

Open **Data sources → Excel upload**. Three steps, one Excel file:

1. **Download the template.** One workbook with a "Start here" sheet and a sheet per kind of record. Only three are
   needed: **Students** (one row per student), **Marks** (one row per student, subject and semester) and
   **Attendance** (one row per student per week). LMS, Other details (placement training, skills, activities,
   feedback), Past actions and Past placements are optional. A **filled example** (360 sample CSE students) shows
   what goes where.
2. **Upload the filled file** (or one CSV per sheet). It is checked at once and every problem is explained in plain
   words ("14 rows have a roll number that is not in Students").
3. **Type the college name and press "Build my dashboard".** Semesters, the current week and the departments are read
   from the file. About a minute later every page uses the new data. If anything goes wrong, nothing changes.
   **"Switch back to the sample college"** returns to the demo data.

Three rules: the same Roll No in every sheet; Semester means the semester number (1 to 8); include this semester and
the two before it (the early warning learns from the two past semesters). Column names can differ a little
("CIA 1", "Internal 1", "Reg No", "Total Classes", "Present" all work), any roll-number style and any department names
work, grades can be letters or grade points, and internal marks can be out of 50 or 100.

Tested with a college that looks nothing like the sample (10-digit numeric roll numbers, EEE and AI & DS, first-year
students, an even semester, grade points, marks out of 100, three CSV files only): with just the three required sheets
the early warning still caught 70% of failing students by week 6, against 46% for the usual lists.

IT teams can instead upload raw exports from each system (12 files with different IDs) under **Advanced**; that is how
the sample college is built.

### The data (synthetic, deliberately messy)

`data/raw/` holds 12 files exported "from" 9 campus systems, each identifying students differently:

| File | System | How it identifies a student |
|---|---|---|
| 01_sis_student_master | SIS / ERP | Roll No `23CS045` (the master ID) |
| 02_exam_cell_results | Exam cell | 12-digit register no, some damaged by Excel (`4.12723E+11`) |
| 03_attendance_weekly | Attendance | Roll No in mixed formats (`23cs045`, ` 23CS045 `, `23CS45`) |
| 04a/04b_lms | Moodle LMS | LMS user id + login email (some personal Gmail) |
| 05_student_affairs_events | Student affairs | Only name + department + year, with spelling variants |
| 06_placement_training_scores | Placement vendor | Register no, official email or personal email |
| 07_skills_assessment | Skills platform | `23-CS-045` |
| 08a/08b feedback | Faculty portal, Google Form | Lower-case roll no / respondent email |
| 09_intervention_log_past | Mentors | Past actions and when |
| 10_alumni_placement_outcomes | Placement cell | Last year's graduates and who got placed |

`_ground_truth_DO_NOT_USE.csv` records what the generator really did (who had a disengagement episode). It is only for
checking the generator and is **never read by the models or dashboard**.

### Code

```
app.py                 starts the app and builds the page menu
views/                 one file per page (login, dashboard, students, profile, analytics, segments, ...)
src/ui.py              shared look, data loading, student lists with View buttons
src/connector.py       read-only connection to the college ERP / Moodle servers, default queries, date -> week
src/demo_server.py     builds the demo college server (ERP + Moodle databases) from the sample college
src/sync.py            nightly sync from the command line (cron / Task Scheduler)
src/build.py           installs new data and rebuilds, putting the old data back if anything fails
src/simple_upload.py   the one-workbook template: checks, column-name matching, conversion
src/sources.py         the list of raw source files, required columns, and file recognition (advanced upload)
src/generate_data.py   builds the synthetic college and its messy exports
src/integrate.py       cleaning + identity matching + quality report
src/features.py        weekly behaviour features, academic history
src/models.py          early-warning model (with back-test) + placement model
src/scoring.py         Student Success Score and its exact contributions
src/segments.py        segment rules and playbooks
src/whatif.py          what-if simulator and Path to Green
src/analytics.py       what works, fairness, insights
src/ai.py, src/nlq.py  optional Gemini layer + plain-English query parser (with offline fallbacks)
src/pipeline.py        runs everything, writes data/processed/
docs/SUCCESS_SCORE_NOTE.md   the required note on the score
```

---

## 3-minute demo script

1. **Sign in, Dashboard (20 s).** "191 students are at high risk this week, 15 of them new. Here's the trend, the mix of
   academic and placement risk, and who to contact first."
2. **Analytics, the proof chart (30 s).** "Tested on a semester it had never seen: by week 6 it caught 78% of the students
   who went on to fail. The usual attendance and marks lists caught 41%."
3. **Student profile (60 s).** Press View on a student. Overview: key facts, the factors pulling the score down, why they
   are flagged. Show the LMS tab (activity dropping) and the Action plan tab (smallest plan back on track, conversation
   guide). Press "Create action plan".
4. **Segments and Placement (40 s).** "129 students have good marks but aren't job-ready. One more mock interview roughly
   doubles the odds of getting placed; a certificate adds 13%."
5. **Interventions (20 s).** Show suggested actions and statuses, then press "Generate report".
6. **Data sources (30 s).** Choose the demo college server and press "Sync now and build". "EarlySignal connects
   read-only to the college ERP and Moodle, the way colleges actually store data: 855,290 period-wise attendance
   rows read in seconds, every night, no spreadsheets. Colleges without database access upload one Excel file instead."
7. **Close.** "Not just a dashboard: an early-warning system that tells each mentor what to do this week."
