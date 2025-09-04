# News Application Project

A Django-based news platform for readers, journalists, and editors. Readers can subscribe to publishers or journalists, receive notifications, and access approved articles. Journalists and editors manage content and workflow.

## Features
- User Roles: Reader, Journalist, Editor (with role-based permissions)
- Article Management: Create, update, delete, and approve articles
- Approval Workflow: Editors review and approve submitted articles
- Subscriptions: Readers subscribe to publishers/journalists
- Notifications: Email alerts for new published articles
- RESTful API: Retrieve articles and newsletters via API
- Twitter Integration: Auto-post published articles to Twitter (requires API keys)
- Unit Testing: Comprehensive test suite for models, views, and APIs

## Setup & Installation

### Using Python Virtual Environment (venv)
1. Clone the repository:
   ```bash
   git clone https://github.com/nandi-y/news_application_project
   cd news_application_project
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Mac/Linux
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure secrets:
   - Create a `.env` file in the project root for sensitive info (e.g., passwords, tokens).
   - **Do NOT commit secrets to the repository.**
   - Example:
     ```env
     SECRET_KEY=your_secret_key
     DB_PASSWORD=your_db_password
     ```
5. Apply migrations and run the server:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

### Using Docker Compose
1. Create a `.env` file in the project root with your secrets (see above).
2. Start the app and database together:
   ```bash
   docker-compose up --build
   ```
   This will build and start both the Django app and MariaDB database.
3. Access the app:
   - Open your browser to `http://localhost:8000` (or the provided port in Docker Playground).
4. Stop the stack:
   ```bash
   docker-compose down
   ```

## Documentation
- User and API documentation is available in `docs/build/html/index.html`.
- If documentation is missing, rebuild with:
  ```bash
  python -m sphinx -b html docs/source docs/build/html
  ```

## Sensitive Information
- **Do NOT commit secrets (passwords, tokens, etc.) to the repository.**
- Add your secrets to a `.env` file (not tracked by git) and configure your Django settings to read from it.

## Testing
Run all tests:
```bash
python manage.py test
```

## License
MIT License

---

