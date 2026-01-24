#!/usr/bin/env python
import asyncio
import httpx
import os
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def check_telegram():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    if not token:
        # Cargar desde .env
        with open('.env') as f:
            for line in f:
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    token = line.split('=', 1)[1].strip()
                    break
    
    if not token:
        print('ERROR: No token')
        return
    
    # Obtener updates pendientes sin confirmar
    url = f'https://api.telegram.org/bot{token}/getUpdates'
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params={'limit': 10})
        data = resp.json()
        
        if data.get('ok'):
            updates = data.get('result', [])
            print(f'Updates pendientes: {len(updates)}')
            for u in updates:
                msg = u.get('message', {})
                text = msg.get('text', '')
                chat_id = msg.get('chat', {}).get('id')
                date = msg.get('date', 0)
                print(f'  - ID:{u.get("update_id")} chat:{chat_id} text="{text[:60]}" date={date}')
        else:
            print(f'Error: {data}')

asyncio.run(check_telegram())
