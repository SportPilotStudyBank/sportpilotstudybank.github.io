import os
import json
import asyncio
import markdown
from bs4 import BeautifulSoup
import edge_tts

# --- CONFIGURATION ---
INPUT_FOLDER = "docs"
OUTPUT_FOLDER = "docs/audio"
VOICE = "en-US-AriaNeural"
SEC_PER_CHAR = 0.065 

# --- PRONUNCIATION & PAUSE MAP ---
PRONUNCIATION_MAP = {
    # Weather & Acronyms
    "METAR": "mee-tar", "METARs": "mee-tars",
    "TAF": "taff", "TAFs": "taffs",
    "SIGMET": "sig-met", "SIGMETs": "sig-mets",
    "AIRMET": "air-met", "AIRMETs": "air-mets",
    "PIREP": "pie-rep", "PIREPs": "pie-reps",
    "AWOS": "A-woss", "ASOS": "A-soss", "ATIS": "A-tiss",
    "CTAF": "see-taff", "UNICOM": "you-nee-com",
    "NOTAM": "no-tam", "NOTAMs": "no-tams",
    
    # Parts & Tech
    "fuselage": "fyu-suh-laaj",
    "empennage": "em-puh-naaj",
    "aileron": "ay-luh-ron", "ailerons": "ay-luh-rons",
    "pitot": "pee-tow",
    "longeron": "lawn-juh-ron",
    "monocoque": "mon-uh-coke", "semimonocoque": "semi-mon-uh-coke",
    "stabilator": "stay-bill-ay-ter",
    "canard": "kuh-nard",
    "nacelle": "nuh-sell",
    "camber": "kam-bur",
    "dihedral": "die-hee-drul",
    "Bernoulli": "bur-noo-lee",
    
    # Regs
    "FAA": "F-A-A", "CFR": "C-F-R", "NTSB": "N-T-S-B",
    "ICAO": "eye-kay-oh", "LSA": "L-S-A",
    "AFM": "A-F-M", "POH": "P-O-H",
    "VFR": "V-F-R", "IFR": "I-F-R",
    "AGL": "A-G-L", "MSL": "M-S-L",
    "IMSAFE": "im-safe"
}

# Define Pause Durations (in seconds)
PAUSE_SECTION = 1.2  # Pause after a Header (## Title)
PAUSE_ITEM = 0.6     # Pause after a bullet point

async def generate_chapter(text, output_base):
    mp3_path = f"{output_base}.mp3"
    
    # 1. Prepare Text for Audio (Inject SSML Tags)
    # We replace our secret tokens with real SSML breaks
    ssml_text = text.replace("||SECTION_PAUSE||", f'<break time="{int(PAUSE_SECTION*1000)}ms"/>')
    ssml_text = ssml_text.replace("||ITEM_PAUSE||", f'<break time="{int(PAUSE_ITEM*1000)}ms"/>')
    
    # Wrap in <speak> so EdgeTTS knows it is SSML
    ssml_text = f"<speak version='1.0' xml:lang='en-US'>{ssml_text}</speak>"
    
    communicate = edge_tts.Communicate(ssml_text, VOICE)
    await communicate.save(mp3_path)
    
    # 2. Prepare Data for Visual Reader (The Math)
    words = []
    current_time = 0.0
    
    # Split text into words (tokens are still in here as "words" right now)
    raw_words = text.split()
    
    for w in raw_words:
        # CHECK FOR PAUSES
        if "||SECTION_PAUSE||" in w:
            current_time += PAUSE_SECTION
            continue # Do not add this token to the visual list
            
        if "||ITEM_PAUSE||" in w:
            current_time += PAUSE_ITEM
            continue # Do not add this token to the visual list

        # ESTIMATE WORD DURATION
        duration = len(w) * SEC_PER_CHAR
        if w.endswith('.') or w.endswith(','):
            duration += 0.15
            
        words.append({
            "word": w,
            "start": round(current_time, 2),
            "end": round(current_time + duration, 2)
        })
        current_time += duration

    return words

def clean_markdown(md_text):
    # Convert MD to HTML first so we can find structure reliably
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    
    # INJECT PAUSE TOKENS into the HTML structure
    
    # 1. After Headers (h1, h2, h3...)
    for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
        header.append(" ||SECTION_PAUSE|| ")
        
    # 2. After List Items (li) - creates pause between bullets
    for li in soup.find_all('li'):
        li.append(" ||ITEM_PAUSE|| ")

    # Extract text (now containing our tokens)
    text = soup.get_text(separator=' ')
    
    # Clean up whitespace
    clean_text = ' '.join(text.split())
    
    # APPLY PRONUNCIATION FIXES
    for word, phonetic in PRONUNCIATION_MAP.items():
        # Replace whole words only
        clean_text = clean_text.replace(f" {word} ", f" {phonetic} ")
        # Also handle cases where the word has punctuation attached
        clean_text = clean_text.replace(f" {word}.", f" {phonetic}.")
        
    return clean_text

async def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    files = sorted([f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.md')])
    
    for filename in files:
        print(f"Processing {filename}...")
        base_name = os.path.splitext(filename)[0]
        
        with open(os.path.join(INPUT_FOLDER, filename), 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        clean_text = clean_markdown(raw_text)
        output_base = os.path.join(OUTPUT_FOLDER, base_name)
        
        words = await generate_chapter(clean_text, output_base)
        
        # Save JSON
        json_path = f"{output_base}.json"
        data = {
            "metadata": {"title": base_name, "audio_file": f"{base_name}.mp3"},
            "words": words
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        print(f"   [+] Saved {len(words)} words (with pauses).")

if __name__ == "__main__":
    asyncio.run(main())
