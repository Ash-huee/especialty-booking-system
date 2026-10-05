"""Convenience script to start the development server.

Run from the `especialty/` directory:

    python run.py
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
