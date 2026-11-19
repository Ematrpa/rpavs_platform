# RPAVS Platform

Frappe app for RPAVS platform features that are stored in ERPNext and are not payroll.
New platform integrations go here.

## Platform Feedback (RPAVS-49)

Supervisors submit feedback from the "We Would Love Your Feedback" card on the
platform dashboard. The Django proxy (`rpavsbackend`, `POST /api/feedback/`)
creates a **Platform Feedback** record with the user's own ERPNext token.

- **Fields:** Title, Category (Enhancement Request, Process Improvement, Platform
  Feedback, General Suggestion, Other), Description, Status (New → Under Review →
  Planned → Implemented / Closed), Internal Notes (only reviewers can see them).
- **Submitter:** `submitted_by`, `submitted_on`, `employee` and `company` are set by
  the server from the session. Values sent by the client are ignored, and reviewers
  cannot change them later.
- **Permissions:** any logged-in user (role **All**: Client Admin, Client Supervisor,
  contractors, ...) can create feedback and read their own records. **Feedback Reviewer** reads and updates all of them.
  System Manager has full access.
- **Email:** the standard Notification **New Platform Feedback** emails every user
  with the **Feedback Reviewer** role. To change who gets it, add or remove the role
  on those users. No deploy needed. The site needs a default outgoing Email Account.
- **Metrics:** the **Feedback** workspace shows Total / New / This Month number cards
  plus Trend, By Category and By Status charts.

## Hiring Requests (RPAVS-44)

Client Admins tell Recruiting about an upcoming contractor position from the
"Planning to add a new contractor?" card on the platform dashboard, or from the
**Hiring Requests** page. The Django proxy (`POST /api/hiring-requests/`) creates a
**Hiring Request** with the user's own ERPNext token.

- **Fields:** Position Title, Experience Level, Location, Expected Start Date, Required
  Skills, Additional Notes, Status (New → In Review → Sourcing → Filled / Closed),
  Internal Notes (only recruiters can see them).
- **Submitter:** set by the server from the session, same as Platform Feedback.
- **Permissions:** only **Client Admin** can create requests, and they only read their own.
  **Recruiter** reads and updates all of them. System Manager has full access.
- **Experience levels:** the **Hiring Experience Level** list (Junior, Mid, Senior at first).
  Recruiters add, rename, reorder (Display Order) or disable levels from the desk; the
  platform form picks up the change with no deploy. The defaults are only inserted
  while the list is empty.
- **Email:** every enabled row in **Hiring Request Settings → Email New Requests To**
  gets each new request (template `templates/emails/new_hiring_request.html`). Recruiter and
  System Manager edit the list from the desk: add rows, or untick Enabled to pause someone.
  It starts with scortez@rpapm.com, added once on install or by the v0_2 patch; it is not
  refilled later, and an empty list sends no email.
- **Desk:** the **Hiring Requests** workspace (Recruiter, System Manager), with links to
  requests, experience levels and settings.

## Contractor Handbook (RPAVS-56)

Contractors read the handbook page by page in the platform (bookshelf icon next to the
avatar, `/handbook`). Every page viewed and the final acknowledgment are stored in
ERPNext, so back office can prove who read which version and when.

- **Handbook:** title, version, PDF (must be a private file; the page count is read
  from it), acknowledgment text, and **Excluded Companies**. Only one handbook is
  Active; activating one deactivates the others. Version "2027" is created once from
  `data/RPA_Virtual_Staffing_Handbook.pdf` (install or the v0_3 patch), excluding
  Real Property Associates Property Management, Real Property Funding Group,
  RPA Maintenance, RPA Brokerage and RPA Virtual Staffing.
- **Who sees it:** every active Employee linked to the user whose company is not
  excluded. Edit the exclusions from the desk; no deploy needed.
- **Handbook Read Progress:** one record per employee and handbook version: furthest
  page, last page, %, status (Not Started → In Progress → Read → Acknowledged),
  first opened, last activity, completed, and on acknowledgment the date, IP address,
  browser and the exact statement accepted. Read-only in the desk, with change
  history. Progress never goes back and an acknowledgment cannot be withdrawn.
- **API** (`rpavs_platform.api.handbook`, called by the Django proxy with the user's
  own token): `get_my_handbook`, `get_my_handbook_file`, `record_page` (pages must be
  read in order), `acknowledge` (only after the last page), and
  `get_progress_report` (HR Manager or System Manager; includes employees who never
  opened it).
- **Permissions:** employees have none on these DocTypes; the methods above act for
  them. HR Manager manages handbooks and reads progress. System Manager has full access.
- **New version:** create a new Handbook (new version, private PDF, same exclusions)
  and mark it Active. Everyone must read and acknowledge it again; earlier records stay.
- **Fix a wrong version label:** click the title → Rename. Existing progress and
  acknowledgments move to the new name (same document, nothing to read again).
- **Hide it:** untick Active on the handbook.

Give the **HR Manager** role to the back office users who check handbook progress.

## Install

Frappe Cloud: push this folder to its own GitHub repo, add it to the bench
(Bench → Apps → Add App), deploy, then install it on the site.

Self-hosted bench:

    bench get-app /path/to/rpavs_platform     # or a git URL
    bench --site erp.rpa-hub.com install-app rpavs_platform
    bench restart

After installing, give the **Feedback Reviewer** role to the back office users who
review feedback (Jeniffer, Sam, Michelle, Landon).

## Tests

    bench --site <test-site> run-tests --app rpavs_platform
