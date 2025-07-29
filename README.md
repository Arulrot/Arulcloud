# ArulCloud: Secure Cloud Storage Web App

<img width="1247" height="832" alt="Screenshot 2025-07-02 143644" src="https://github.com/user-attachments/assets/8a23df23-929b-4784-b3fd-491410f5c3ea" />

ArulCloud is a user-friendly and secure cloud storage web application, built with Flask and AWS, that allows users to easily upload, preview, download, rename, and manage files with storage plans and user authentication via AWS Cognito.

## Features

- **User Authentication via AWS Cognito**:  
  Secure sign-up, login, and email verification.
- **File Management via Amazon S3**:  
  Upload, preview, download, rename, and delete your files, stored safely on S3.
- **User Storage Plans**:  
  Multiple tiers: Free, Silver, Gold, Premium, with corresponding quotas.
- **Storage Usage Dashboard**:  
  Instantly check current usage, file-list, and plan information.
- **AWS RDS (MySQL)**:  
  Persistent storage of users and plan data.
- **Secure Sessions**:  
  Flask session configuration with enhanced security options.
- **Role-based Access**:  
  Protected endpoints with robust login restriction.
- **AWS Secrets Manager**:  
  Load configuration and secrets at runtime, never stored in code.

----

## Architecture

**Tech Stack**:
- **Backend:** Python 3, Flask, pymysql
- **Frontend:** Flask Jinja templates, HTML/CSS
- **Cloud Services:**  
  - Amazon Cognito (User Management)
  - Amazon S3 (File Storage)
  - Amazon RDS (MySQL, User Data)
  - AWS Secrets Manager (Keys & Config)

**Directory Structure:**
```
.
├── app.py
├── templates/
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── main.html
│   ├── plans.html
│   └── verify.html
├── static/
│   └── sounds
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.8+
- AWS Account (with Cognito, S3, RDS, Secrets Manager access)
- IAM credentials with proper permissions
- Pip: Flask, Boto3, PyMySQL, Werkzeug

### Installation

1. **Clone this repo:**
    ```sh
    git clone https://github.com/Arulrot/arulcloud.git
    cd arulcloud
    ```

2. **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

3. **Configure AWS & Environment:**

    - Create all AWS resources:
      - Cognito User Pool and App Client
      - S3 bucket for file storage
      - RDS MySQL DB instance
      - Store all secrets (User Pool ID, Client ID/Secret, DB host/user/pass, bucket name, etc.) in AWS Secrets Manager under the secret name `arulcloud-secconfig`.

    - Example SecretsManager JSON (no trailing commas):
      ```json
      {
        "USER_POOL_ID": "your-pool-id",
        "CLIENT_ID": "your-client-id",
        "CLIENT_SECRET": "your-client-secret",
        "REGION": "ap-south-1",
        "S3_BUCKET": "your-bucket-name",
        "RDS_HOST": "xx.xx.xx.xx",
        "RDS_USER": "dbuser",
        "RDS_PASSWORD": "dbpass",
        "RDS_DB": "aruldatabase"
      }
      ```

    - Ensure your environment is authorized for AWS API access (set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` etc. if not default).

4. **Prepare the Database:**
    - The app will auto-create all necessary tables on first run.

5. **Launch the App:**
    ```sh
    python app.py
    ```
    - App runs on `http://localhost:5000`.

## Endpoints

| Path                | Methods | Auth Required | Purpose                  |
|---------------------|---------|---------------|--------------------------|
| `/`                 | GET     | No            | Home Page                |
| `/register`         | GET/POST| No            | Register new user        |
| `/verify`           | GET/POST| No            | Email verification       |
| `/login`            | GET/POST| No            | Login page               |
| `/main`             | GET     | Yes           | User dashboard           |
| `/upload`           | POST    | Yes           | Upload files             |
| `/rename`           | POST    | Yes           | Rename file              |
| `/preview/`   | GET     | Yes           | Preview file             |
| `/download/`  | GET     | Yes           | Download file            |
| `/delete/`    | GET     | Yes           | Delete file              |
| `/upgrade_plan`     | POST    | Yes           | Upgrade storage plan     |
| `/plans`            | GET     | Yes           | View plans               |
| `/logout`           | GET     | No            | Log out                  |

## Security

- **All secrets stored in AWS Secrets Manager; never in code.**
- **Session cookies secure (`SESSION_COOKIE_SECURE = True`).**
- **All endpoints (except login/register/home) require authentication.**
- **Files isolated per-user in S3, using email prefix.**
- **Password hash verification handled by AWS Cognito; no passwords stored in app database.**

## Deployment

For production deployments:
- Set `debug=False`
- Deploy behind a WSGI server (e.g. Gunicorn)
- Serve via HTTPS (required for secure cookies)
- Harden IAM permissions for least-privilege principle


## Contact / Contributing

**Pull requests are welcome!**  
For significant changes, please open an issue first.

Email: [iamarulmohan333@gmail.com]  
GitHub: [github.com/Arulrot]

**Enjoy using ArulCloud!**
