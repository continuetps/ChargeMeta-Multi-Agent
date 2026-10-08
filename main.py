"""ChargeMeta Agent local entrypoint."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("chargemeta.main:app", host="0.0.0.0", port=8000, reload=True)
