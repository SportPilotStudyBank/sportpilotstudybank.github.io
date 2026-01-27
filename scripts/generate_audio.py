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

# SPEED CONTROL (0.075 = Matches Aria's speaking rate)
SEC_PER_CHAR = 0.075 

# --- PRONUNCIATION MAP (Only for Audio!) ---
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
    "IMSAFE": "im-safe",
    "Weight & Balance": "Weight and Balance"
}

# Pauses (Simulated in time)
PAUSE_SECTION = 1.0
PAUSE_ITEM = 0.5

def clean_markdown_base(md_text):
    """
    Step 1: Convert Markdown to plain text structure.
    We inject tokens to mark where headers/bullets were.
    """
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    
    # Inject tokens so we know where to pause
    for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
        header.append(" ||SECTION_PAUSE|| ")
        
    for li in soup.find_all('li'):
        li.append(" ||ITEM_PAUSE|| ")

    # Get text
    text = soup.get_text(separator=' ')
    
    # Cleanup whitespace
    return ' '.join(text.split())

def prepare_for_audio(text):
    """
    Step 2: Track A - Make it ready for the ROBOT.
    - Remove hashtags/symbols
    - Apply Pronunciation Map
    - Turn tokens into punctuation for natural pauses
    """
    audio_text = text
    
    # 1. Apply Pronunciations
    for word, phonetic in PRONUNCIATION_MAP.items():
        # Replace word with phonetic version (e.g. "NOTAM" -> "no-tam")
        audio_text = audio_text.replace(f" {word} ", f" {phonetic} ")
        audio_text = audio_text.replace(f" {word}.", f" {phonetic}.")
        audio_text = audio_text.replace(f" {word},", f" {phonetic},")

    # 2. Replace Tokens with Periods (Natural Pauses)
    audio_text = audio_text.replace("||SECTION_PAUSE||", ". ")
    audio_text = audio_text.replace("||ITEM_PAUSE||", ". ")
    
    # 3. CRITICAL: Remove any remaining Markdown symbols the robot reads
    audio_text = audio_text.replace("#", "")
    audio_text = audio_text.replace("*", "")
    audio_text = audio_text.replace("-", "")
    
    return audio_text

def prepare_for_display(text):
    """
    Step 3: Track B - Make it ready for the HUMAN.
    - Keep original spelling (NOTAM)
    - Remove tokens completely (don't show them)
    """
    display_text = text
    
    # Just remove the tokens. Don't replace them with text.
    # We do NOT apply the pronunciation map here.
    display_text = display_text.replace("||SECTION_PAUSE||", "")
    display_text = display_text.replace("||ITEM_PAUSE||", "")
    
    return display_text

async def generate_chapter(base_text, output_base):
    mp3_path = f"{output_base}.mp3"
    
    # --- TRACK A: AUDIO ---
    audio_text = prepare_for_audio(base_text)
    communicate = edge_tts.Communicate(audio_text, VOICE)
    await communicate.save(mp3_path)
    
    # --- TRACK B: VISUALS ---
    # We use the BASE text (with tokens) to calculate timing, 
    # but we save the CLEAN text to the JSON.
    sentences_data = []
    current_time = 0.0
    
    # Split using the BASE text so we don't lose the pause tokens yet
    raw_sentences = re.split(r'(?<=[.!?])\s+', base_text)
    
    for s in raw_sentences:
        if not s.strip(): continue

        pause_add = 0.0
        
        # Calculate timing based on tokens
        if "||SECTION_PAUSE||" in s:
            pause_add += PAUSE_SECTION
            
        if "||ITEM_PAUSE||" in s:
            pause_add += PAUSE_ITEM

        # Create the Human-Readable version for this sentence
        clean_s = prepare_for_display(s).strip()
        
        if not clean_s: continue 
            
        # Estimate duration based on the DISPLAY text length
        duration = len(clean_s) * SEC_PER_CHAR
        
        sentences_data.append({
            "text": clean_s,  # This will say "NOTAM", not "no-tam"
            "start": round(current_time, 2),
            "end": round(current_time + duration, 2)
        })
        
        current_time += duration + pause_add

    return sentences_data

async def main():
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    files = sorted([f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.md')])
    
    for filename in files:
        print(f"Processing {filename}...")
        base_name = os.path.splitext(filename)[0]
        
        with open(os.path.join(INPUT_FOLDER, filename), 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        # 1. Initial Markdown Cleaning (Shared)
        base_text = clean_markdown_base(raw_text)
        
        output_base = os.path.join(OUTPUT_FOLDER, base_name)
        
        try:
            sentences = await generate_chapter(base_text, output_base)
            
            data = {
                "metadata": {"title": base_name, "audio_file": f"{base_name}.mp3"},
                "sentences": sentences
            }
            
            with open(f"{output_base}.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            print(f"   [+] Saved {len(sentences)} sentences.")
        except Exception as e:
            print(f"   [!] Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
