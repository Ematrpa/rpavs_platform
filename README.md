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
