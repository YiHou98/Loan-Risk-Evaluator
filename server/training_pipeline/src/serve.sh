# In your src/ directory
echo '#!/bin/bash
exec gunicorn --bind 0.0.0.0:8080 --workers 1 --timeout 60 --keep-alive 2 server:app' > src/serve

# Make it executable
chmod +x src/serve