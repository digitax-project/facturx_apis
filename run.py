import uvicorn
import os

if __name__ == "__main__":
    host = os.getenv("FACTURX_HOST", "localhost")
    port = int(os.getenv("FACTURX_PORT", "6969"))
    
    print(f"Starting Factur-X API server on http://{host}:{port}")
    print(f"Swagger UI documentation available at http://{host}:{port}/docs")
    uvicorn.run("facturx.api:app", host=host, port=port, reload=True)
