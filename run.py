import uvicorn

if __name__ == "__main__":
    print("Starting Factur-X API server on http://localhost:6969")
    print("Swagger UI documentation available at http://localhost:6969/docs")
    uvicorn.run("facturx.api:app", host="localhost", port=6969, reload=True)
