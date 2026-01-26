import os
import json
import asyncio
import markdown
from bs4 import BeautifulSoup
import edge_tts
from pydub import AudioSegment

# --- CONFIGURATION ---
INPUT_FOLDER = "docs"
OUTPUT_FOLDER = "docs/audio"
VOICE = "en-US-AriaNeural"
CHUNK_SIZE = 2500  # Characters per chunk (Safe limit for EdgeTTS)

async def generate_chunk(text, voice):
    """Generates audio/words for a small text segment"""
    communicate = edge_tts.Communicate(text, voice)
    
    audio_data = b""
    words = []
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            words.append({
                "word": chunk["text"],
                "start": chunk["offset"] / 10_000_000,
                "end": (chunk["offset"] + chunk["duration"]) / 10_000_000
            })
            
    return audio_data, words

def split_text(text, limit):
    """Splits text into chunks without cutting sentences"""
    chunks = []
    current_chunk = ""
    
    # Split by periods first to keep sentences intact
    sentences = text.split('. ')
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < limit:
            current_chunk += sentence + ". "
        else:
            chunks.append(current_chunk)
            current_chunk = sentence + ". "
    
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

def clean_markdown(md_text):
    html = markdown.markdown(md_text)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=' ')

async def process_file(filename):
    print(f"Processing {filename}...")
    base_name = os.path.splitext(filename)[0]
    
    # Read and Clean
    file_path = os.path.join(INPUT_FOLDER, filename)
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    clean_text = clean_markdown(raw_text)

    # Chunking
    text_chunks = split_text(clean_text, CHUNK_SIZE)
    print(f"   > Split into {len(text_chunks)} chunks.")

    final_audio = AudioSegment.empty()
    final_words = []
    time_offset = 0.0

    # Process each chunk
    for i, chunk_text in enumerate(text_chunks):
        print(f"   > Generating chunk {i+1}/{len(text_chunks)}...")
        
        # 1. Generate Raw Audio & Data
        audio_bytes, words = await generate_chunk(chunk_text, VOICE)
        
        if not audio_bytes:
            print("   [!] Warning: Empty audio chunk generated.")
            continue

        # 2. Save temporary file for pydub to read
        temp_file = f"temp_{base_name}_{i}.mp3"
        with open(temp_file, "wb") as f:
            f.write(audio_bytes)
        
        # 3. Load into PyDub to measure exact duration
        segment = AudioSegment.from_mp3(temp_file)
        duration_seconds = len(segment) / 1000.0
        
        # 4. Shift Timestamps and Add to Master List
        for w in words:
            w["start"] += time_offset
            w["end"] += time_offset
            final_words.append(w)
            
        # 5. Append Audio and update offset
        final_audio += segment
        time_offset += duration_seconds
        
        # Cleanup temp file
        os.remove(temp_file)

    # Save Final Files
    output_mp3_path = os.path.join(OUTPUT_FOLDER, f"{base_name}.mp3")
    output_json_path = os.path.join(OUTPUT_FOLDER, f"{base_name}.json")
    
    # Export MP3
    final_audio.export(output_mp3_path, format="mp3")
    print(f"   [+] Saved MP3: {output_mp3_path}")

    # Export JSON
    data = {
        "metadata": {"title": base_name, "audio_file": f"{base_name}.mp3"},
        "words": final_words
    }
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"   [+] Saved JSON: {output_json_path}")

async def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    if not os.path.exists(INPUT_FOLDER):
        print("Error: Input folder not found.")
        return

    files = sorted([f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.md')])
    
    for f in files:
        try:
            await process_file(f)
        except Exception as e:
            print(f"CRITICAL ERROR on {f}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
