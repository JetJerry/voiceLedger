import uvicorn
from backend.app.config import settings

if __name__ == "__main__":
    print(f"\n=======================================================")
    print(f" VoiceLedger running at: http://127.0.0.1:{settings.PORT}")
    print(f" Open http://127.0.0.1:{settings.PORT} in Chrome / Edge")
    print(f"=======================================================\n")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=settings.PORT, reload=True)
