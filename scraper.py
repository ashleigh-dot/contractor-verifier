import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import aiohttp
from cache import get_cached_result, store_result

# State-specific license verification URLs and selectors
STATE_CONFIGS = {
    "CA": {
        "url": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
        "method": "playwright",  # Requires JavaScript
        "license_input": "#ctl00_ContentPlaceHolder1_txtLicnum",
        "search_button": "#ctl00_ContentPlaceHolder1_btnSearch",
        "result_selectors": {
            "status": ".license-status",
            "name": ".contractor-name",
            "expires": ".expiration-date"
        }
    },
    "TX": {
        "url": "https://www.tdlr.texas.gov/LicenseSearch/",
        "method": "playwright",
        "license_input": "#LicenseNumber",
        "search_button": "#SearchButton",
        "result_selectors": {
            "status": ".status-field",
            "name": ".business-name",
            "expires": ".expiration-field"
        }
    },
    "FL": {
        "url": "https://www.myfloridalicense.com/wl11.asp",
        "method": "requests",  # Simple form submission
        "form_data": {
            "licnbr": "{license_number}",
            "Submit": "Search"
        }
    }
    # Add more states as needed
}

async def verify_license_playwright(state_config, license_number, business_name=None):
    """Verify license using Playwright for JavaScript-heavy sites"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to the license verification page
            await page.goto(state_config["url"], wait_until="networkidle")
            
            # Fill in the license number
            if license_number:
                await page.fill(state_config["license_input"], license_number)
            
            # Click search button
            await page.click(state_config["search_button"])
            await page.wait_for_load_state("networkidle")
            
            # Take screenshot for evidence
            screenshot_bytes = await page.screenshot(full_page=True)
            
            # Extract results using the configured selectors
            result_data = {}
            for field, selector in state_config["result_selectors"].items():
                try:
                    element = await page.query_selector(selector)
                    if element:
                        result_data[field] = await element.text_content()
                except:
                    result_data[field] = "Not found"
            
            await browser.close()
            
            return {
                "status": result_data.get("status", "Unknown"),
                "license_number": license_number,
                "business_name": result_data.get("name", "Unknown"),
                "issuing_authority": f"{state_config.get('authority', 'State')} Licensing Board",
                "expires": result_data.get("expires", "Unknown"),
                "screenshot_data": screenshot_bytes,
                "verified": True
            }
            
        except Exception as e:
            await browser.close()
            raise Exception(f"Error scraping license data: {str(e)}")

async def verify_license_requests(state_config, license_number, business_name=None):
    """Verify license using simple HTTP requests"""
    async with aiohttp.ClientSession() as session:
        try:
            # Prepare form data
            form_data = {}
            for key, value in state_config["form_data"].items():
                if "{license_number}" in value:
                    form_data[key] = value.format(license_number=license_number)
                else:
                    form_data[key] = value
            
            # Submit the form
            async with session.post(state_config["url"], data=form_data) as response:
                html_content = await response.text()
                
            # Parse the response
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract license information (customize based on state's HTML structure)
            status = "Unknown"
            business_name_result = "Unknown"
            expires = "Unknown"
            
            # Look for common patterns in license verification results
            if "active" in html_content.lower():
                status = "Active"
            elif "expired" in html_content.lower():
                status = "Expired"
            elif "invalid" in html_content.lower():
                status = "Invalid"
            
            return {
                "status": status,
                "license_number": license_number,
                "business_name": business_name_result,
                "issuing_authority": f"State Licensing Board",
                "expires": expires,
                "verified": True,
                "raw_html": html_content[:1000]  # First 1000 chars for debugging
            }
            
        except Exception as e:
            raise Exception(f"Error verifying license: {str(e)}")

async def verify_license(state, license_number=None, business_name=None):
    """Main license verification function"""
    
    # Check cache first
    cache_key = f"{state}_{license_number}_{business_name}"
    cached = get_cached_result(cache_key)
    if cached:
        return cached
    
    # Validate inputs
    if not state:
        raise Exception("State is required")
    
    if not license_number and not business_name:
        raise Exception("Either license number or business name is required")
    
    state = state.upper()
    
    # Check if we have configuration for this state
    if state not in STATE_CONFIGS:
        return {
            "status": "Unsupported",
            "message": f"License verification not yet supported for {state}",
            "supported_states": list(STATE_CONFIGS.keys()),
            "verified": False
        }
    
    state_config = STATE_CONFIGS[state]
    
    try:
        # Use appropriate scraping method based on state configuration
        if state_config["method"] == "playwright":
            result = await verify_license_playwright(state_config, license_number, business_name)
        else:
            result = await verify_license_requests(state_config, license_number, business_name)
        
        # Cache the result
        store_result(cache_key, result)
        
        return result
        
    except Exception as e:
        return {
            "status": "Error",
            "message": str(e),
            "license_number": license_number,
            "verified": False
        }

async def verify_batch(requests):
    """Verify multiple licenses in batch"""
    tasks = []
    for r in requests:
        task = verify_license(
            r.get("state"),
            r.get("license_number"),
            r.get("business_name")
        )
        tasks.append(task)
    
    # Run all verifications concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error dictionaries
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "status": "Error",
                "message": str(result),
                "license_number": requests[i].get("license_number"),
                "verified": False
            })
        else:
            processed_results.append(result)
    
    return processed_results
