# Student Learning Hub: Demo Script

## 1. Demo Goal

The goal of the demo is to show how Student Learning Hub helps students discover, share, and manage academic resources, and how administrators provide basic moderation.

A good demo should show the complete journey:

1. Discover resources as a visitor.
2. Register and log in as a student.
3. Upload and manage a resource.
4. Preview or download the resource.
5. Show administrator moderation and statistics.
6. Explain the technology and security decisions.

Recommended demo length: 8 to 12 minutes.

## 2. Before the Demo

Prepare the following:

- Start the application using the instructions in `LOCAL_SETUP.md`.
- Open `http://127.0.0.1:5000`.
- Have a small permitted PDF or text file ready for upload.
- Use a new student email address for registration.
- If demonstrating admin features, promote the demo account using the local command in `LOCAL_SETUP.md` or prepare a separate admin account.
- Confirm that the database and upload folder are available.
- Keep the terminal visible or ready in case you need to explain the server output.

Start the application with:

```powershell
cd D:\projects\studentlearning\StudentLearningHub
.\.venv\Scripts\python.exe app.py
```

Run tests before the presentation if needed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 3. Opening Explanation

Use a short introduction like this:

> Student Learning Hub is a Flask-based web application for students to share and discover academic resources. It provides categorized browsing, search, authentication, file uploads, previews, downloads, student dashboards, and administrator moderation. The goal is to keep useful student material organized and easier to access.

Then explain the two types of users:

- Students use the learning and sharing features.
- Administrators review platform activity and moderate users and resources.

## 4. Live Demo Sequence

### Step 1: Show the home page

Open the home page and point out:

- The project name and navigation.
- The category cards.
- The newest resources.
- The login and registration actions.
- The responsive layout if presenting on a small screen.

Say:

> The home page gives visitors an overview of the available learning categories and recently added resources.

### Step 2: Browse, search, and filter

Open the resource browsing page.

1. Search for a word from a resource title or description.
2. Select a category.
3. Move between pages if enough resources exist.
4. Explain that search is case-insensitive and pagination keeps the page manageable.

Say:

> Resources are stored with a category relationship, so the application can filter and count them consistently instead of relying on repeated text values.

### Step 3: Demonstrate access control

While logged out, try to open a resource detail page or download link.

Explain:

> Visitors can browse the resource list, but resource details, previews, and downloads require authentication. This protects uploaded material while still allowing public discovery.

### Step 4: Register and log in

Open the authentication page and register a student account.

Show that:

- The email is normalized to lowercase.
- The account receives the student role by default.
- A user cannot choose the administrator role during registration.
- The password is stored as a hash, not plain text.

Log in and show the authenticated navigation and dashboard.

### Step 5: Upload a resource

Open the upload page and enter:

- A clear title.
- A short description.
- A category.
- The prepared PDF or text file.

Submit the form and show the success message.

Explain:

> The server validates the form, checks the file extension and size, sanitizes the original filename, generates a UUID-based stored filename, and creates a database record linked to the current user and category.

Optional rejection demo: try an `.exe` file or a file larger than 10 MB and show that it is rejected.

### Step 6: Show the dashboard

Open the dashboard and point out the uploaded resource.

Demonstrate:

- Viewing the resource in the user's uploads.
- Editing the profile if appropriate.
- Changing the password if appropriate.
- Deleting the user's own resource.

Explain:

> The ownership relationship allows a student to manage their own uploads without giving them permission to manage other users' resources.

### Step 7: Preview and download

Upload or use a PDF, image, or text file and open its details page.

Show:

- A browser preview for supported formats.
- The download action.

Say:

> Preview support is provided for common browser-readable files. Other allowed file types can be downloaded instead.

### Step 8: Demonstrate the administrator dashboard

Log out and log in with an administrator account. Show:

- Total user count.
- Total resource count.
- Category statistics.
- All resources.
- User list.
- Resource deletion.
- Non-admin user deletion.

Explain:

> Administrator authorization is checked on the server using the user's database role. The Admin link is only a navigation convenience; the actual protection is enforced by the route logic.

### Step 9: Close the demo

Finish with:

> The application demonstrates a complete student resource workflow from discovery to upload and moderation. It is ready as a local academic prototype, while production deployment would require stronger file inspection, email integration, stable production configuration, and additional tests.

## 5. Common Questions and Answers

### What problem does this project solve?

It centralizes student learning material and makes it searchable, categorized, previewable, and downloadable instead of leaving resources scattered across personal folders or messages.

### Why did you choose Flask?

Flask is lightweight and flexible. It provides routing, request handling, sessions, templates, and error handling while keeping the project structure easy to understand for an academic application.

### Why use SQLite?

SQLite is easy to run locally because it does not require a separate database server. The application still uses SQLAlchemy, so the database URL can be changed for another relational database later.

### Why use a separate Category model?

A category table prevents inconsistent repeated text, supports relationships and counts, and makes filtering more reliable.

### How are passwords protected?

The application stores password hashes created with Werkzeug. It checks a submitted password against the hash during login instead of storing or comparing plain-text passwords.

### How do you prevent someone from becoming an admin during registration?

Registration always creates the `student` role. Administrator promotion is a separate controlled local/database operation, and admin routes verify the role on the server.

### How are uploaded files protected?

The application limits file size, restricts extensions, sanitizes filenames, and stores files using generated UUID names. Uploads are associated with the authenticated user and a category.

### Is extension checking enough for production?

No. It is useful basic validation for this prototype, but production should inspect file contents and MIME signatures, scan for malware, enforce quotas, and isolate uploaded files from executable application content.

### Can a visitor download a resource?

A visitor can browse the resource list, but login is required for details, previews, and downloads.

### Does forgot-password send an email?

No. The current local prototype generates a one-hour reset link and displays it on-screen. A production version would send a time-limited link through an email service.

### Does the contact form save messages?

No. It validates required fields and displays a confirmation message, but it does not currently store or send the message.

### Can administrators edit categories?

No. The current admin dashboard can view category statistics, but category creation, renaming, and deletion are not implemented.

### What happens if two users upload files with the same name?

The original name is displayed for users, but the stored file receives a UUID-based name, so files do not overwrite each other because of matching original filenames.

### What happens if a user deletes an upload?

The application removes the resource record and its associated stored file according to the deletion workflow. Administrators can also delete resources.

### How does CSRF protection work?

Flask-WTF provides CSRF protection for forms. A valid token is required for form submissions, which helps prevent another site from submitting actions on behalf of a logged-in user.

### How is the application tested?

Pytest tests core routes and workflows such as page access, registration, login, access control, categories, duplicate registration, and basic upload behavior. More edge-case tests would be useful for production readiness.

### Is this ready for production?

It is suitable for a local demonstration and academic prototype. Before production, it would need a stable secret key, production database and WSGI configuration, email integration, stronger upload security, malware scanning, more complete tests, and deployment hardening.

## 6. Questions to Ask the Audience

These can make the presentation interactive:

- Which resource category would be most useful for students?
- Should resources be public, private, or visible only to registered users?
- Should the contact form create support tickets or send email notifications?
- What additional moderation rules should an administrator have?
- Should the application support ratings, comments, bookmarks, or resource versioning?

## 7. Emergency Recovery During the Demo

If an upload fails:

- Confirm that the file extension is allowed.
- Confirm that the file is smaller than 10 MB.
- Check that the user is logged in.
- Use a simple PDF or text file.
- Check the Flask terminal for the error.

If the admin link is missing:

- Confirm that the account role is `admin`.
- Log out and log in again after changing the role.
- Use the administrator promotion command in `LOCAL_SETUP.md`.

If the database is empty:

- Restart the application so the built-in categories can be seeded.
- Register a new account and upload a sample resource.

## 8. Final Presentation Summary

End with three points:

1. The application organizes and shares student learning resources.
2. Flask, SQLAlchemy, WTForms, SQLite, JavaScript, and CSS work together to provide the complete workflow.
3. The current version is a functional local prototype with clear next steps for production hardening.
