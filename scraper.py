from cache import get_cached_result, store_result

async def verify_license(state, license_number=None, business_name=None):
    # Replace this with actual scraping logic
    return {
        "status": "Active",
        "license_number": license_number or "UNKNOWN",
        "issuing_authority": f"{state} Contractors Board",
        "expires": "2026-12-31",
        "screenshot_url": "https://example.com/screenshot.png"
    }

async def verify_batch(requests):
    return [
        await verify_license(
            r.get("state"),
            r.get("license_number"),
            r.get("business_name")
        )
        for r in requests
    ]
