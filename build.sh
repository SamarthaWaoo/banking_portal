#!/usr/bin/env bash
# Build script for Render (or any similar host).
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

#!/usr/bin/env bash
# ============================================================
#  build.sh — Run once after cloning / pulling updates.
#  Usage: bash build.sh
# ============================================================
set -e

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Running migrations..."
python manage.py migrate

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "✅  Done. Start the server with:"
echo "    python manage.py runserver"
