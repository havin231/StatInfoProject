import os
from app import create_app

# Create an instance of the application using the factory function
app = create_app()

if __name__ == '__main__':
    # Controlled via FLASK_DEBUG env var (defaults to False for production safety)
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(debug=debug_mode)
