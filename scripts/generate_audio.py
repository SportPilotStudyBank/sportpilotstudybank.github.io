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

# Speaking Rate (Seconds per character). 
# 0.06 is fast, 0.07 is slow. Aria is usually around 0.065.
SEC_PER_CHAR = 0.065 

async def generate_chapter(text, output_base):
    mp3_path = f"{output_base}.mp3"
    
    # 1. Generate Audio (We just save it directly)
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(mp3_path)
    
    # 2. Generate Timestamps (The "Math" Method)
    # This guarantees we have words, even if the API fails to send data.
    words = []
    current_time = 0.0
    
    # Split text into words
    raw_words = text.split()
    
    for w in raw_words:
        # how long does it take to say this word?
        duration = len(w) * SEC_PER_CHAR
        
        # Add a tiny buffer for punctuation pauses
        if w.endswith('.') or w.endswith(','):
            duration += 0.15
            
        words.append({
            "word": w,
            "start": round(current_time, 2),
            "end": round(current_time + duration, 2)
        })
        
        # Advance the clock
        current_time += duration

    return words

def clean_markdown(md_text):
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    # Clean up extra whitespace/newlines
    text = soup.get_text(separator=' ')
    return ' '.join(text.split())

async def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    files = sorted([f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.md')])
    
    for filename in files:
        print(f"Processing {filename}...")
        base_name = os.path.splitext(filename)[0]
        
        # Read
        with open(os.path.join(INPUT_FOLDER, filename), 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        clean_text = clean_markdown(raw_text)
        output_base = os.path.join(OUTPUT_FOLDER, base_name)
        
        # Generate
        words = await generate_chapter(clean_text, output_base)
        
        # Save JSON
        json_path = f"{output_base}.json"
        data = {
            "metadata": {"title": base_name, "audio_file": f"{base_name}.mp3"},
            "words": words
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        print(f"   [+] Saved {len(words)} words to JSON.")

if __name__ == "__main__":
    asyncio.run(main())
