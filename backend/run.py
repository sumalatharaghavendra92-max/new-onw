from dotenv import load_dotenv
import os

# Load .env from the backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import create_app

app = create_app()

if __name__ == '__main__':
    # threaded=True so overlapping GPS-log requests (fired every few seconds
    # during live tracking) don't queue up behind each other on Flask's dev server.
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=5000, threaded=True)
