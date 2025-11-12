from fastapi import FastAPI

app = FastAPI(title="Trading Engine API", version="0.1.0")


@app.get("/")
async def hello_world():
    """Hello world endpoint."""
    return {"message": "Hello World"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


def main():
    """Entry point for the application."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
