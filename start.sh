#!/bin/bash
cd "$(dirname "$0")"
python3 -c "from app import app; app.run(host='0.0.0.0', port=5000)"
