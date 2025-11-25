from fastapi import FastAPI
from app.api.api_router import api_router

app = FastAPI()


@app.get("/")
def root():
    return {"message": "backend is running"}


# include all API routes from the central api_router
app.include_router(api_router)
