# Student Learning Hub: Project Guide

## 1. Project Overview

Student Learning Hub is a Flask web application that helps students share, find, and manage academic learning resources in one place. Resources can include practical programs, project code, seminar presentations, documentation, coding practice, interview preparation, resumes, and useful links.

The application has two main audiences:

- **Students:** browse, search, preview, download, and upload learning resources.
- **Administrators:** review resources, manage users, and monitor platform statistics.

The application is designed as a local academic project and prototype. It demonstrates a complete web application workflow: authentication, database storage, file uploads, search, authorization, and responsive frontend behavior.

## 2. Problem It Solves

Students often keep useful notes and project material in different folders, chat messages, or websites. This makes resources difficult to find and share. Student Learning Hub provides:

- A central place for learning materials.
- Categories so resources are easier to organize.
- Search and filtering so users can find relevant material quickly.
- Preview and download options for supported files.
- User accounts so uploads and actions can be associated with a person.
- Administrator controls for basic moderation.

## 3. Main Features

### Home page

The home page introduces the platform, shows the available categories, and displays the newest resources. This gives visitors an immediate view of what the platform contains.

### Resource browsing

Users can browse resources using:

- Case-insensitive search across resource titles and descriptions.
- Category filtering.
- Pagination, with up to 12 resources per page.
- Resource cards and detail pages.

The resource list is publicly visible, while opening resource details, previews, and downloads requires login.

### User registration and login

A new account is created as a student account by default. Registration:

- Requires a name, email, and password.
- Converts the email to lowercase.
- Prevents duplicate email addresses.
- Does not allow a visitor to register as an administrator.

Passwords are stored as secure hashes rather than plain text. Login requests are rate-limited to reduce repeated automated attempts.

The login form says "Email / Username," but the current implementation authenticates using the email address only.

### Student dashboard

Logged-in students can:

- View their uploaded resources.
- Upload new resources.
- Delete their own resources.
- Edit their profile.
- Change their password.

### Resource upload

An upload contains a title, description, category, and file. The application:

- Limits uploads to 10 MB.
- Allows only configured file extensions.
- Sanitizes the original filename with `secure_filename`.
- Generates a UUID-based stored filename to avoid collisions.
- Associates the resource with the logged-in uploader and selected category.

Supported examples include PDF files, common Office files, archives, text files, and common image formats.

### Resource preview and download

Logged-in users can preview PDFs, images, and text files in the browser. Other allowed file types can be downloaded. The application uses the original file extension to select the preview MIME type.

### Administrator dashboard

Administrators can view:

- Total users.
- Total resources.
- Category counts.
- All uploaded resources.
- Registered users.

Administrators can delete resources and delete non-admin users together with their uploaded resources. Admin permissions are checked on the server, so hiding an Admin link in the navigation is not the only protection.

Categories can be viewed and counted, but category creation, renaming, and deletion are not currently implemented.

### Password recovery

The forgot-password flow validates the email and creates a one-hour reset token. In this local prototype, the reset URL is displayed on-screen rather than sent by email. This demonstrates the workflow without requiring an email service.

### Contact form

The contact page validates that the required fields are not empty and displays a success message. It does not currently save the message or send it to an administrator.

## 4. How the Application Works

The typical resource workflow is:

1. A visitor opens the Flask application.
2. Flask renders the home page using a Jinja2 template.
3. A user registers or logs in.
4. The user submits an upload form protected by CSRF validation.
5. Flask validates the form and file extension.
6. The file is saved with a generated filename in `static/uploads/`.
7. A `Resource` database record stores the title, description, category, uploader, original filename, stored filename, and creation date.
8. The resource appears in search results, category results, and the uploader dashboard.
9. An authenticated user can view, preview, or download it.
10. The owner or an administrator can delete it.

## 5. Data Model

The application uses three SQLAlchemy models.

### User

Stores the user's name, unique email, password hash, role, creation date, and password-reset fields.

### Category

Stores a stable key, display name, description, and the resources assigned to that category. The project seeds eight built-in categories.

### Resource

Stores the resource title, description, original filename, generated stored filename, file path, category, uploader, and creation date.

Relationships:

- One user can upload many resources.
- One category can contain many resources.
- Each resource belongs to one user and one category.

Using a separate category table avoids repeating category text in every resource record and makes filtering and counting more reliable.

## 6. Technologies Used and Why

| Technology | Purpose | Why it is used |
| --- | --- | --- |
| Python | Application language | Clear syntax and a large web development ecosystem. |
| Flask 3.1 | Web framework | Handles routes, requests, sessions, templates, and errors with a lightweight structure. |
| Jinja2 | HTML templating | Renders dynamic server-side pages while reusing shared layouts. |
| Flask-SQLAlchemy | Database ORM | Maps Python models to database tables and simplifies queries and relationships. |
| SQLite | Default database | Simple local relational storage with no separate database server required. |
| Flask-WTF and WTForms | Forms and validation | Provides structured forms, validation, and CSRF protection. |
| Flask-Limiter | Rate limiting | Limits authentication POST requests to 10 per minute per IP. |
| Werkzeug | Passwords and filenames | Provides password hashing, password checking, and safe filename handling. |
| python-dotenv | Configuration | Loads settings such as `SECRET_KEY` and `DATABASE_URL` from `.env`. |
| Vanilla JavaScript | Browser interactions | Powers mobile navigation, tab switching, validation, toast dismissal, animation, and drag-and-drop upload behavior without a frontend framework. |
| CSS | Visual design | Provides the responsive layout, cards, colors, animations, and mobile styling. |
| Pytest | Testing | Tests routes, authentication, access control, registration, categories, and upload behavior. |

## 7. Application Structure

- `app.py`: Flask application, routes, authentication, authorization, uploads, previews, downloads, and error handling.
- `config.py`: Application configuration, database location, upload settings, allowed extensions, and secret key settings.
- `models.py`: SQLAlchemy models and database relationships.
- `forms.py`: WTForms definitions and validation rules.
- `template/`: Jinja2 HTML templates for pages and shared layout.
- `static/script.js`: Browser-side interactions.
- `static/style.css`: Responsive visual styling.
- `tests/test_routes.py`: Automated route and workflow tests.
- `instance/student_learning_hub.db`: Local SQLite database created by the application.
- `static/uploads/`: Locally uploaded files.

## 8. Security and Validation

The implemented protections include:

- Password hashing with Werkzeug.
- Global CSRF protection for forms.
- Rate limiting on login and registration POST requests.
- Server-side administrator authorization checks.
- Safe original filenames using `secure_filename`.
- UUID-based stored filenames.
- A 10 MB upload limit.
- An allowlist of accepted file extensions.
- Generic responses for unknown password-recovery emails.

These controls make the project safer for a local demonstration, but they are not a complete production security system.

## 9. Current Limitations

Be clear about these points when presenting the project:

- Upload validation checks the file extension, not the actual file contents or MIME signature.
- There is no malware scanning, duplicate detection, storage quota, or content moderation.
- Password recovery displays a link on-screen and does not send email.
- Contact messages are not saved or emailed.
- Categories are seeded and viewable, but there is no category management interface.
- The default secret key can change between application restarts unless `SECRET_KEY` is configured.
- The test suite does not cover every feature, including all preview, download, deletion, password-reset, pagination, and rate-limit cases.

For production use, the project would need a stable secret key, production database configuration, email integration, stronger file inspection, malware scanning, broader tests, and a production WSGI server.

## 10. Setup Summary

From PowerShell:

```powershell
cd D:\projects\studentlearning\StudentLearningHub
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000` in a browser. The complete reusable setup instructions are in [LOCAL_SETUP.md](LOCAL_SETUP.md).
