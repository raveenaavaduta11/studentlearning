# Production Deployment on Vercel

## Important architecture

- Vercel runs this Flask app as a serverless Python function.
- SQLite is for local development only. Use hosted PostgreSQL in production.
- Vercel's filesystem is temporary. Uploaded resources must move to Cloudinary, Amazon S3, or another object-storage provider before production uploads are enabled.

## 1. Create a hosted PostgreSQL database

Create a database with Neon, Supabase, or another PostgreSQL provider. Copy its connection string, usually beginning with `postgresql://`.

## 2. Deploy the project

From the project folder:

```powershell
npm install -g vercel
vercel login
vercel
```

When Vercel asks for the project directory, use the folder containing `vercel.json`.

For a production deployment:

```powershell
vercel --prod
```

## 3. Add Vercel environment variables

In Vercel project settings, add these variables for the Production environment:

```text
SECRET_KEY=<long-random-secret>
DATABASE_URL=<hosted-postgresql-connection-string>
FLASK_DEBUG=0
CLOUDINARY_CLOUD_NAME=<cloudinary-cloud-name>
CLOUDINARY_API_KEY=<cloudinary-api-key>
CLOUDINARY_API_SECRET=<cloudinary-api-secret>
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=<brevo-login-email>
SMTP_PASSWORD=<brevo-smtp-key>
SMTP_FROM_EMAIL=<verified-sender-email>
SMTP_CONTACT_RECIPIENT=<support-inbox-email>
SMTP_USE_TLS=1
SMTP_USE_SSL=0
```

Redeploy after adding or changing environment variables.

A local `.env` can use the same names. Never commit `.env`; use `.env.example` as the template.

## 4. Initialize the database

The current app calls `db.create_all()` during startup, which creates the tables in the configured PostgreSQL database on the first deployment. For future schema changes, use migrations instead of relying on `create_all()`.

## 5. File uploads with Cloudinary

Create a free Cloudinary account and copy the three values from its dashboard. When all three variables are present, uploads go to Cloudinary automatically and downloads/previews redirect to the permanent Cloudinary URL. When they are absent, local development continues to use `static/uploads/`.

Do not commit the API secret. Add all three Cloudinary variables to Vercel's Production environment.

## 6. Password-reset email

Configure an SMTP provider and add `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `SMTP_CONTACT_RECIPIENT` to Vercel's Production environment.
The default uses STARTTLS on port 587. Set `SMTP_USE_SSL=1` for providers that
require implicit TLS, such as port 465. Reset tokens are sent only by email and
are never displayed in the browser.

The free tier is suitable for a college demo, but review its storage and bandwidth limits before broad public use.

## 7. Verify deployment

Open the Vercel URL and test:

- registration and login
- category creation during upload
- resource upload and download
- admin category/resource controls

## 8. Short URL for the college

After `vercel --prod`, Vercel gives the project a URL such as `student-learning-hub.vercel.app`. Use that URL as the college demo link. You can also set a short custom domain in Vercel's Domains settings, such as `slh-demo.vercel.app`, if the name is available.

The Vercel entrypoint is `api/index.py` and its routing is defined in `vercel.json`.
