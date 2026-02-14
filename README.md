# 🦁 Curio-Group-Management-App

A Django-based platform for managing projects in group settings, with the implementation of AI.

---

## 📂 Project Structure
We are using a **Django Templates** architecture (HTML inside Django).

```text
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

COMMAND:
git clone (https://github.com/<your-name>/Curio-Group-Management-App.git)
cd Curio-Group-Management-App
git checkout dev


2. Set Up Virtual Environment
Create the isolated Python environment.

♟️Windows COMMAND :

python -m venv venv
venv\Scripts\activate

♟️Mac/Linux COMMAND:

python3 -m venv venv
source venv/bin/activate
(You should see (venv) in your terminal now).

3. Install Dependencies

♟️COMMAND:
pip install django

4. Run the Server
Navigate to the backend and start Django.

♟️COMMAND:
cd backend
python manage.py migrate       # Sets up the database
python manage.py runserver     # Starts the site

🎉 Open http://127.0.0.1:8000/ in your browser.


👩‍💻 How to Contribute
NEVER push directly to main.

💠Update: git checkout dev -> git pull origin dev

💠Branch: git checkout -b <your-name>/<feature> (e.g., faith/login-page)

💠Work: Write your code.

💠Frontend: Edit HTML in backend/templates/ and CSS in backend/static/.

💠Backend: Edit views.py and models.py.

💠Save: git add . -> git commit -m "Description of work"

💠Upload: git push origin <your-branch-name>

💠Merge: Go to GitHub and create a Pull Request to merge into dev.


🆘 Troubleshooting

📌"manage.py not found"

Fix: You are in the wrong folder. Run: cd backend

📌"No such table" (Database Error)

Fix: Your database is out of sync. Run: python manage.py migrate

📌"Port 8000 already in use"

Fix: Close your other terminal or run: python manage.py runserver 8001

📌"No module named django"

Fix: Your virtual environment is off. Run: source venv/bin/activate (Mac) or venv\Scripts\activate (Windows).

📌"TemplateDoesNotExist"

Fix: You put the HTML file in the wrong folder. Move it to backend/templates/.



Happy coding and all the best!



