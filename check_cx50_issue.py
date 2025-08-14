#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager

db = DatabaseManager()

# Check if CX-50 review exists
cx50 = db.supabase.table('clips').select('wo_number, make, model, sentiment_completed').eq('wo_number', '1197437').single().execute()
print('CX-50 Review (WO 1197437):')
print(f'  Make: {cx50.data.get("make")}')
print(f'  Model: {cx50.data.get("model")}') 
print(f'  Sentiment Completed: {cx50.data.get("sentiment_completed")}')

# Check all Mazda CX-50 reviews
print('\nAll Mazda CX-50 reviews in database:')
all_cx50 = db.supabase.table('clips').select('wo_number, make, model, sentiment_completed').eq('make', 'Mazda').eq('model', 'CX-50').execute()
print(f'Found {len(all_cx50.data)} CX-50 reviews')
for clip in all_cx50.data:
    print(f'  {clip["wo_number"]}: sentiment_completed={clip["sentiment_completed"]}')

# Check OEM messaging
print('\nCX-50 OEM messaging:')
oem_cx50 = db.supabase.table('oem_model_messaging').select('make, model, year').eq('make', 'Mazda').eq('model', 'CX-50').execute()
for msg in oem_cx50.data:
    print(f'  {msg["make"]} {msg["model"]} ({msg["year"]})')