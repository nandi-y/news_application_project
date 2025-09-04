# News Application Project

## Setup & Installation

### Using Python Virtual Environment (venv)
1. Clone the repository:
   ```
   git clone <your-repo-url>
   cd <repo-folder>
   ```
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Mac/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run migrations and start the server:
   ```
   python manage.py migrate
   python manage.py runserver
   ```

### Using Docker
1. Build the Docker image:
   ```
   docker build -t news-app .
   ```
2. Run the container:
   ```
   docker run -p 8000:8000 news-app
   ```

## Sensitive Information
- **Do NOT commit secrets (passwords, tokens, etc.) to the repository.**
- Add your secrets to a `.env` file (not tracked by git) and configure your Django settings to read from it.

## Documentation
- User and API documentation is available in `docs/build/html/index.html`.

## Troubleshooting
- If documentation is missing, rebuild with:
  ```
  python -m sphinx -b html docs/source docs/build/html
  ```

---
For further help, contact the maintainer or book a mentor call.
