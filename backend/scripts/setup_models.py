import httpx
import asyncio
import json
import sys

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:3b"

async def pull_model():
    print(f"Connecting to Ollama at {OLLAMA_URL}...")
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            # Check if ollama is running
            resp = await client.get(OLLAMA_URL)
            if resp.status_code != 200:
                print("Ollama is not responding correctly.")
                return

            print(f"Pulling model {MODEL}... This may take a while depending on your internet connection.")
            
            # Using httpx stream to show progress
            async with client.stream("POST", f"{OLLAMA_URL}/api/pull", json={"name": MODEL}) as response:
                if response.status_code != 200:
                    print(f"Failed to pull model: {response.status_code}")
                    print(await response.aread())
                    return
                
                async for chunk in response.aiter_bytes():
                    if chunk:
                        # Sometimes chunks contain multiple JSON objects separated by newlines
                        lines = chunk.decode('utf-8').strip().split('\n')
                        for line in lines:
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                status = data.get('status', '')
                                completed = data.get('completed', 0)
                                total = data.get('total', 1)
                                if total > 1 and 'download' in status.lower():
                                    percent = (completed / total) * 100
                                    sys.stdout.write(f"\r{status}: {percent:.1f}%")
                                    sys.stdout.flush()
                                else:
                                    # Just print status if it's not downloading (e.g. verifying, pulling manifest)
                                    sys.stdout.write(f"\r{status}{' ' * 20}")
                                    sys.stdout.flush()
                            except json.JSONDecodeError:
                                pass
            print("\nModel pulled successfully!")

    except httpx.RequestError as e:
        print(f"\nError connecting to Ollama: {e}")
        print("Please ensure Ollama is running and accessible at localhost:11434")

if __name__ == "__main__":
    asyncio.run(pull_model())
