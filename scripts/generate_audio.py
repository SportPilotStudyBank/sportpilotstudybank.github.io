import os
import json
import asyncio
import re
import markdown
from bs4 import BeautifulSoup
import edge_tts

# --- CONFIGURATION ---
INPUT_FOLDER = "docs"
OUTPUT_FOLDER = "docs/audio"
VOICE = "en-US-AriaNeural"
SEC_PER_CHAR = 0.065 

# --- PRONUNCIATION MAP ---
PRONUNCIATION_MAP = {
    "METAR": "mee-tar", "METARs": "mee-tars",
    "TAF": "taff", "TAFs": "taffs",
    "SIGMET": "sig-met", "SIGMETs": "sig-mets",
    "AIRMET": "air-met", "AIRMETs": "air-mets",
    "PIREP": "pie-rep", "PIREPs": "pie-reps",
    "AWOS": "A-woss", "ASOS": "A-soss", "ATIS": "A-tiss",
    "CTAF": "see-taff", "UNICOM": "you-nee-com",
    "NOTAM": "no-tam", "NOTAMs": "no-tams",
    "fuselage": "fyu-suh-laaj", "empennage": "em-puh-naaj",
    "aileron": "ay-luh-ron", "pitot": "pee-tow",
    "stabilator": "stay-bill-ay-ter", "canard": "kuh-nard",
    "FAA": "F-A-A", "CFR": "C-F-R", "NTSB": "N-T-S-B",
    "ICAO": "eye-kay-oh", "LSA": "L-S-A",
    "VFR": "V-F-R", "IFR": "I-F-R", "AGL": "A-G-L", "MSL": "M-S-L",
    "IMSAFE": "im-safe"
}

# Pause Durations
PAUSE_SECTION = 1.2
PAUSE_ITEM = 0.6

async def generate_chapter(text, output_base):
    mp3_path = f"{output_base}.mp3"
    
    # 1. Generate Audio (with SSML pauses)
    ssml_text = text.replace("||SECTION_PAUSE||", f'<break time="{int(PAUSE_SECTION*1000)}ms"/>')
    ssml_text = ssml_text.replace("||ITEM_PAUSE||", f'<break time="{int(PAUSE_ITEM*1000)}ms"/>')
    ssml_text = f"<speak version='1.0' xml:lang='en-US'>{ssml_text}</speak>"
    
    communicate = edge_tts.Communicate(ssml_text, VOICE)
    await communicate.save(mp3_path)
    
    # 2. Generate Sentence Timestamps
    sentences_data = []
    current_time = 0.0
    
    # Split text into sentences using Regex
    # Looks for punctuation (.!?) followed by space or end of string
    raw_sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for s in raw_sentences:
        if not s.strip(): continue # Skip empty lines

        # Detect and handle pauses inside this sentence block
        pause_add = 0.0
        clean_s = s
        
        if "||SECTION_PAUSE||" in s:
            pause_add += PAUSE_SECTION
            clean_s = clean_s.replace("||SECTION_PAUSE||", "").strip()
            
        if "||ITEM_PAUSE||" in s:
            pause_add += PAUSE_ITEM
            clean_s = clean_s.replace("||ITEM_PAUSE||", "").strip()
            
        if not clean_s: continue # If it was just a pause token, skip adding text
            
        # Estimate duration of the sentence
        duration = len(clean_s) * SEC_PER_CHAR
        
        sentences_data.append({
            "text": clean_s,
            "start": round(current_time, 2),
            "end": round(current_time + duration, 2)
        })
        
        # Advance time (Speech duration + Pause duration)
        current_time += duration + pause_add

    return sentences_data

def clean_markdown(md_text):
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    
    for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
        header.append(" ||SECTION_PAUSE|| ")
    for li in soup.find_all('li'):
        li.append(" ||ITEM_PAUSE|| ")

    text = soup.get_text(separator=' ')
    clean_text = ' '.join(text.split())
    
    for word, phonetic in PRONUNCIATION_MAP.items():
        clean_text = clean_text.replace(f" {word} ", f" {phonetic} ")
        clean_text = clean_text.replace(f" {word}.", f" {phonetic}.")
        
    return clean_text

async def main():
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    files = sorted([f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.md')])
    
    for filename in files:
        print(f"Processing {filename}...")
        base_name = os.path.splitext(filename)[0]
        
        with open(os.path.join(INPUT_FOLDER, filename), 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        clean_text = clean_markdown(raw_text)
        output_base = os.path.join(OUTPUT_FOLDER, base_name)
        
        sentences = await generate_chapter(clean_text, output_base)
        
        data = {
            "metadata": {"title": base_name, "audio_file": f"{base_name}.mp3"},
            "sentences": sentences  # Changed from 'words' to 'sentences'
        }
        
        with open(f"{output_base}.json", 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        print(f"   [+] Saved {len(sentences)} sentences.")

if __name__ == "__main__":
    asyncio.run(main())
