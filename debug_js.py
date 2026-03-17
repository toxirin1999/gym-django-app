import asyncio
import sys
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        logs = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: logs.append(f"[pageerror] {err.message}"))
        
        # Adding a session cookie for User ID 2 so we are authenticated
        # Use an existing active session or let's just attempt to see if there's syntax errors
        # To make sure we don't get redirected, let's create a quick valid session using Django
        # Actually, let's just open the page, even if redirected, syntax errors in the JS won't show.
        
        pass

if __name__ == '__main__':
    # Need to generate a sessionid
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings')
    import django
    django.setup()
    
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore
    
    user = User.objects.filter(cliente__id=2).first()
    if not user:
        user = User.objects.first()
        
    session = SessionStore()
    session['_auth_user_id'] = str(user.pk)
    session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
    session['_auth_user_hash'] = user.get_session_auth_hash()
    session.create()
    sessionid = session.session_key
    
    async def main_with_cookie():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            await context.add_cookies([{
                'name': 'sessionid',
                'value': sessionid,
                'domain': 'localhost',
                'path': '/'
            }])
            page = await context.new_page()
            
            # Catch console
            logs = []
            page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: logs.append(f"[pageerror] {err.message}"))
            
            await page.goto("http://localhost:8000/entrenos/cliente/2/plan/", wait_until="networkidle")
            
            # Print logs
            for log in logs:
                print(log)
                
            await browser.close()
            
    asyncio.run(main_with_cookie())
