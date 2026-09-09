import asyncio
import json
from app.services.ai_extractor import DocumentExtractionService

async def main():
    print("Testing AI Extractor with Ollama...")
    
    sample_ocr = """
    INCOME TAX DEPARTMENT
    GOVT. OF INDIA
    
    XYZPA1234B
    
    Rahul Sharma
    
    15/08/1985
    """
    
    print("Sending OCR text to Ollama...")
    result = await DocumentExtractionService.extract_fields(sample_ocr, "PAN_CARD")
    
    if result.success:
        print("Extraction Successful!")
        print(json.dumps(result.data, indent=2))
        print(f"Confidence: {result.confidence_score}")
    else:
        print(f"Extraction Failed: {result.error}")

if __name__ == "__main__":
    asyncio.run(main())
