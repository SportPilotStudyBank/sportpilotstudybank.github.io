import os
import json
import asyncio
import markdown
from bs4 import BeautifulSoup
import edge_tts

# --- CONFIGURATION ---
INPUT_FOLDER = "docs"
OUTPUT_FOLDER = "docs/audio"  # Keep generated files separate from source text
VOICE = "en-US-AriaNeural"

async def generate_chapter(text, output_base):
    mp3_path = f"{output_base}.mp3"
    
    # 1. Generate Audio + Subtitles (VTT)
    communicate = edge_tts.Communicate(text, VOICE)
    submaker = edge_tts.SubMaker()
    
    with open(mp3_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    # 2. Convert Subtitles to JSON
    vtt_content = submaker.generate_subs()
    words = parse_vtt_to_json(vtt_content)
    
    return words

def parse_vtt_to_json(vtt_content):
    lines = vtt_content.split('\n')
    words = []
    current_word = {}
    
    for line in lines:
        line = line.strip()
        if '-->' in line:
            start_str, end_str = line.split(' --> ')
            current_word['start'] = time_str_to_seconds(start_str)
            current_word['end'] = time_str_to_seconds(end_str)
        elif line and not line.isdigit() and line != 'WEBVTT':
            current_word['word'] = line
            if 'start' in current_word:
                words.append(current_word)
                current_word = {}
    return words

def time_str_to_seconds(time_str):
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def clean_markdown(md_text):
    # Convert MD to HTML then strip tags for clean reading
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=' ')

async def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # Only process .md files, ignoring other things in docs/
    files = sorted([f for f in os.listdir(INPUT_FOLDER) if f.endswith('.md')])
    
    for filename in files:
        print(f"Processing {filename}...")
        base_name = os.path.splitext(filename)[0]
        
        # Read MD from docs/
        with open(os.path.join(INPUT_FOLDER, filename), 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        clean_text = clean_markdown(raw_text)
        
        # Output to docs/audio/
        output_base = os.path.join(OUTPUT_FOLDER, base_name)
        words = await generate_chapter(clean_text, output_base)
        
        # Save JSON
        json_path = f"{output_base}.json"
        data = {
            "metadata": {
                "title": base_name, 
                "audio_file": f"{base_name}.mp3"
            },
            "words": words
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
