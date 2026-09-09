from playwright.async_api import async_playwright, Page, Browser, Playwright
import logging
import asyncio
import os
import base64

logger = logging.getLogger(__name__)

class PortalAutomationService:
    def __init__(self, mock_portal_url: str = "http://localhost:3000/mock-udyam"):
        self.mock_portal_url = mock_portal_url
        self._playwright: Playwright = None
        self._browser: Browser = None
        self._page: Page = None
        self.session_id: str = None
        
    async def start_session(self, session_id: str):
        """Starts a headless Playwright session."""
        self.session_id = session_id
        logger.info(f"Starting Playwright session: {self.session_id}")
        
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._page = await self._browser.new_page()
        
        try:
            # Navigate to the mock portal. 
            # In a real scenario, this mock portal might be hosted on the frontend Next.js app
            await self._page.goto(self.mock_portal_url)
            logger.info("Successfully navigated to the mock portal.")
        except Exception as e:
            logger.error(f"Failed to navigate to {self.mock_portal_url}: {e}")
            raise

    async def fill_initial_form(self, aadhaar_number: str, name: str):
        """Fills the first page of the Udyam registration form."""
        if not self._page:
            raise RuntimeError("Playwright session not started.")
            
        logger.info("Filling initial form...")
        try:
            # Wait for elements (assuming standard IDs for the mock portal)
            await self._page.wait_for_selector("#aadhaar_number", timeout=15000)
            await self._page.fill("#aadhaar_number", aadhaar_number)
            
            await self._page.wait_for_selector("#applicant_name", timeout=15000)
            await self._page.fill("#applicant_name", name)
            
            await self._page.click("#btn_validate_generate_otp")
            logger.info("Initial form submitted, waiting for OTP page.")
            
        except Exception as e:
            logger.error(f"DOM Timeout or Error filling form: {e}")
            await self.capture_error_state("DOM_TIMEOUT")
            raise

    async def capture_screenshot(self) -> str:
        """Captures a screenshot of the current page and returns it as a base64 string."""
        if not self._page:
            return ""
            
        screenshot_bytes = await self._page.screenshot(type="jpeg", quality=80)
        base64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
        return base64_img
        
    async def capture_error_state(self, error_type: str):
        """Takes a screenshot and saves it to a storage directory for debugging."""
        if not self._page:
            return
            
        error_dir = os.path.join(os.getcwd(), "storage", "errors")
        os.makedirs(error_dir, exist_ok=True)
        
        file_path = os.path.join(error_dir, f"{self.session_id}_{error_type}.jpg")
        await self._page.screenshot(path=file_path, type="jpeg", quality=80)
        logger.error(f"Error state captured and saved to {file_path}")

    async def close(self):
        """Cleans up the Playwright session."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info(f"Closed Playwright session: {self.session_id}")
