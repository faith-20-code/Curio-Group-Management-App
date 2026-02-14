# Curio-Group-Management-App
A Django-based platform for managing projects in group settings, with the implementation of Ai.

📂 Project Structure
We are using a Django Templates architecture (HTML inside Django).

curio-management-platform/
├── backend/
│   ├── config/              # Project settings (urls.py, settings.py)
│   ├── accounts/            # App for Login/Signup/Profile
│   ├── groups/              # App for Group logic
│   ├── notifications/       # App for Alerts
│   ├── templates/           # ALL HTML FILES GO HERE
│   │   ├── base.html        # Shared layout (navbar)
│   │   ├── accounts/        # HTML for login/signup
│   │   └── groups/          # HTML for group views
│   └── static/              # CSS, JS, Images
│       ├── css/
│       └── js/
└── venv/                    # Virtual Environment (Ignored by Git)

🚀 Getting Started
Follow these steps to set up the project on your laptop.

1. Clone & Branch
Always work on the dev branch or your own feature branch.

GIT COMMANDS :
💠git clone https://github.com/YOUR_USERNAME/curio-group-management-app.git
💠cd curio-group-management-app
💠git checkout dev


2. Set Up Virtual Environment
Create the isolated Python environment.

COMMANDS:
# Windows
💠python -m venv venv
💠venv\Scripts\activate

# Mac/Linux
💠python3 -m venv venv
💠source venv/bin/activate
(You should see (venv) in your terminal now).

3. Install Dependencies
COMMANDS:
💠pip install django

4. Run the Server
Navigate to the backend and start Django.

COMMANDS:
💠cd backend
💠python manage.py migrate       # Sets up the database
💠python manage.py runserver     # Starts the site
🎉 Open http://127.0.0.1:8000/ in your browser.

👩‍💻 How to Contribute
NEVER push directly to main.

Update: git checkout dev -> git pull origin dev (to make sure you have the updated code)

Branch: git checkout -b <your-name>/<feature> (e.g., faith/login-page)

Work: Write your code.

Frontend: Edit HTML in backend/templates/ and CSS in backend/static/.

Backend: Edit views.py and models.py in your specific app.

Save: git add . -> git commit -m "Description of work"

Upload: git push origin <your-branch-name> (eg faith/login-page)

Merge: Go to GitHub and create a Pull Request to merge into dev.


🆘 Troubleshooting
💠"Module not found": Did you activate your venv? (source venv/bin/activate)

💠"TemplateDoesNotExist": Did you put your HTML file in backend/templates/APP_NAME/?

💠"Database error": Run python manage.py migrate.

Happy coding and all the best!



