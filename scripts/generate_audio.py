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

async def generate_chapter(text, output_base):
    mp3_path = f"{output_base}.mp3"
    
    communicate = edge_tts.Communicate(text, VOICE)
    
    words = []
    
    # We will write audio bytes immediately to the file
    with open(mp3_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            
            elif chunk["type"] == "WordBoundary":
                # DIRECT ACCESS: Parse the raw events directly
                # EdgeTTS provides offset/duration in 'ticks' (1 tick = 100 nanoseconds)
                # 1 second = 10,000,000 ticks
                
                start_seconds = chunk["offset"] / 10_000_000
                duration_seconds = chunk["duration"] / 10_000_000
                end_seconds = start_seconds + duration_seconds
                
                words.append({
                    "word": chunk["text"],
                    "start": start_seconds,
                    "end": end_seconds
                })

    return words

def clean_markdown(md_text):
    # Convert MD to HTML then strip tags for clean reading
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    # Get text with space separators to prevent words merging
    return soup.get_text(separator=' ')

async def main():
    # 1. Setup Directories
    if not os.path.exists(OUTPUT_FOLDER):
        print(f"Creating directory: {OUTPUT_FOLDER}")
        os.makedirs(OUTPUT_FOLDER)

    # 2. Find Markdown Files
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: Input folder '{INPUT_FOLDER}' does not exist.")
        return

    # Case-insensitive search for .md files
    all_files = os.listdir(INPUT_FOLDER)
    files = sorted([f for f in all_files if f.lower().endswith('.md')])
    
    print(f"Found {len(files)} markdown files in {INPUT_FOLDER}")

    for filename in files:
        print(f"Processing {filename}...")
        base_name = os.path.splitext(filename)[0]
        
        # Read MD from docs/
        file_path = os.path.join(INPUT_FOLDER, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        clean_text = clean_markdown(raw_text)
        
        # Output to docs/audio/
        output_base = os.path.join(OUTPUT_FOLDER, base_name)
        
        try:
            words = await generate_chapter(clean_text, output_base)
            print(f"   [+] Generated audio: {base_name}.mp3")
            
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
            print(f"   [+] Saved sync data: {base_name}.json")
            
        except Exception as e:
            print(f"   [!] Error processing {filename}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
