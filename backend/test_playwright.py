import asyncio
from app.services.portal_automation import PortalAutomationService

async def main():
    print("Testing Playwright Automation...")
    # We use google.com just to test if playwright can launch and take a screenshot, 
    # since we don't have the mock portal running yet.
    service = PortalAutomationService(mock_portal_url="https://www.google.com")
    
    try:
        await service.start_session(session_id="test_session_123")
        
        print("Capturing screenshot...")
        b64 = await service.capture_screenshot()
        print(f"Screenshot captured! Base64 string length: {len(b64)}")
        
        print("Capturing error state to disk...")
        await service.capture_error_state("TEST_ERROR")
        
    except Exception as e:
        print(f"Playwright test failed: {e}")
    finally:
        await service.close()

if __name__ == "__main__":
    asyncio.run(main())
