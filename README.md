# 🎓 CampusHire — Campus Hiring System

A full-stack web application that connects **students** with **recruiters** through a streamlined campus placement portal, managed by an **admin**.

---

## 📁 Project Structure

```
campus_hiring/
└── backend/
    ├── app.py                  ← Main Flask application + DB setup
    ├── requirements.txt        ← Python dependencies
    ├── campus_hiring.db        ← SQLite database (auto-created on first run)
    ├── routes/
    │   ├── auth.py             ← Login, Signup, Logout
    │   ├── student.py          ← Student dashboard, jobs, applications
    │   ├── recruiter.py        ← Job posting, applicant management
    │   └── admin.py            ← Admin panel, user management
    ├── templates/
    │   ├── base.html           ← Shared layout with sidebar
    │   ├── auth/               ← Login & Signup pages
    │   ├── student/            ← Student dashboard, profile, jobs, applications
    │   ├── recruiter/          ← Recruiter dashboard, job management, applicants
    │   └── admin/              ← Admin panel, user list, job monitor
    └── static/
        ├── css/style.css       ← All styles (clean, modern UI)
        └── uploads/resumes/    ← Uploaded PDF resumes stored here
```

---

## 🚀 Setup & Run

### 1. Install Python dependencies

```bash
cd campus_hiring/backend
pip install -r requirements.txt
```

### 2. Run the application

```bash
python app.py
```

The app will:
- Create the SQLite database automatically
- Seed sample data (admin, recruiter, student accounts + sample jobs)
- Start the server at **http://localhost:5000**

---

## 🔑 Sample Login Credentials

| Role      | Email                      | Password       |
|-----------|----------------------------|----------------|
| 🎓 Student   | student@college.edu        | student123     |
| 🏢 Recruiter | recruiter@techcorp.com     | recruiter123   |
| 🛠️ Admin     | admin@campus.edu           | admin123       |

---

## 👤 User Roles & Features

### 🎓 Student
- View dashboard with stats (jobs available, applications, shortlists, interviews)
- Edit profile (college, degree, branch, CGPA, skills, phone)
- Upload PDF resume (max 5 MB)
- Browse and search/filter job listings
- Apply to jobs with optional cover letter
- Track application status (Applied → Shortlisted → Selected/Rejected)
- View scheduled interview details

### 🏢 Recruiter
- Sign up (requires admin approval before first login)
- Create, manage, activate/deactivate, and delete job postings
- View all applicants per job with their profiles and CGPA
- Download student resumes (PDF)
- Update application status
- Schedule/reschedule interviews (date, time, mode, location, notes)

### 🛠️ Admin
- Approve or reject recruiter signups
- View all students and recruiters
- Revoke recruiter access
- Delete users
- Monitor all job postings (activate/deactivate any job)
- View system analytics (total users, jobs, applications, interviews)
- Application status breakdown with progress bars
- Real-time activity feed

---

## 🗄️ Database Schema

| Table                | Description                              |
|----------------------|------------------------------------------|
| `users`              | All accounts with role & approval status |
| `student_profiles`   | Extended student info + resume path      |
| `recruiter_profiles` | Company info for recruiters              |
| `jobs`               | Job postings with all details            |
| `applications`       | Student–job applications with status     |
| `interviews`         | Scheduled interviews linked to apps      |

---

## 🔌 Routes Overview

| Method | URL                                        | Description                    |
|--------|--------------------------------------------|--------------------------------|
| GET/POST | `/login`                                 | Login page                     |
| GET/POST | `/signup`                                | Signup page                    |
| GET    | `/logout`                                  | Logout                         |
| GET    | `/student/dashboard`                       | Student home                   |
| GET/POST | `/student/profile`                       | Edit student profile           |
| POST   | `/student/upload-resume`                   | Upload PDF resume              |
| GET    | `/student/jobs`                            | Browse & filter jobs           |
| GET    | `/student/jobs/<id>`                       | Job detail page                |
| POST   | `/student/apply/<id>`                      | Apply to a job                 |
| GET    | `/student/applications`                    | My applications                |
| GET    | `/student/interviews`                      | My interviews                  |
| GET    | `/recruiter/dashboard`                     | Recruiter home                 |
| GET/POST | `/recruiter/profile`                     | Edit recruiter profile         |
| GET    | `/recruiter/jobs`                          | Manage all jobs                |
| GET/POST | `/recruiter/jobs/create`                 | Create new job                 |
| POST   | `/recruiter/jobs/<id>/toggle`              | Activate/deactivate job        |
| POST   | `/recruiter/jobs/<id>/delete`              | Delete job                     |
| GET    | `/recruiter/jobs/<id>/applicants`          | View applicants                |
| POST   | `/recruiter/applications/<id>/status`      | Update application status      |
| GET/POST | `/recruiter/applications/<id>/schedule`  | Schedule interview             |
| GET    | `/recruiter/resume/<filename>`             | Download student resume        |
| GET    | `/admin/dashboard`                         | Admin analytics                |
| GET    | `/admin/users`                             | All users (filterable)         |
| POST   | `/admin/users/<id>/approve`                | Approve/reject recruiter       |
| POST   | `/admin/users/<id>/delete`                 | Delete user                    |
| GET    | `/admin/jobs`                              | All jobs monitor               |
| POST   | `/admin/jobs/<id>/toggle`                  | Toggle job visibility          |

---

## 🔒 Security Notes

- Passwords are stored in plain text in this demo — use `werkzeug.security.generate_password_hash` for production
- Add CSRF protection using Flask-WTF for production
- Use environment variables for `SECRET_KEY` in production

---

## ⚡ Tech Stack

- **Backend:** Python 3.x + Flask 3.0
- **Database:** SQLite (via Python's built-in `sqlite3`)
- **Frontend:** Jinja2 templates + CSS (no frontend framework)
- **Fonts:** Google Fonts (Sora + DM Mono)
- **File Upload:** Werkzeug secure file handling
