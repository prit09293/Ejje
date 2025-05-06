from telethon import events, TelegramClient
import os
import asyncio
import time

# Telegram API credentials
api_id = 2282111
api_hash = 'da58a1841a16c352a2a999171bbabcad'
guessSolver = TelegramClient('saitama/temp', api_id, api_hash)
chatid = -1002083282328  # Change this to your group/channel ID

from telethon.tl.types import PhotoStrippedSize

# Variables to track response and retries
last_guess_time = 0
guess_timeout = 15  # Time to wait for a response after /guess
pending_guess = False  # Track if waiting for a response
retry_lock = asyncio.Lock()  # Prevent concurrent retries

# Ensure cache directory exists
os.makedirs("cache", exist_ok=True)
os.makedirs("saitama", exist_ok=True)

# Send /guess command and track the time
async def send_guess_command():
    global last_guess_time, pending_guess
    try:
        await guessSolver.send_message(entity=chatid, message='/guess')
        print("Sent /guess command to chat.")
        last_guess_time = time.time()
        pending_guess = True  # Mark as awaiting response
    except Exception as e:
        print(f"Error in sending /guess: {e}")
        await asyncio.sleep(10)  # Retry after 10 seconds if it fails
        await send_guess_command()

# Detect "Who's that Pokémon?" game logic and respond
@guessSolver.on(events.NewMessage(from_users=572621020, pattern="Who's that pokemon?", chats=(int(chatid)), incoming=True))
async def guess_pokemon(event):
    global last_guess_time, pending_guess
    try:
        pending_guess = False  # Reset pending status on valid response
        for size in event.message.photo.sizes:
            if isinstance(size, PhotoStrippedSize):
                size = str(size)
                # Check if the Pokémon's data already exists in the cache
                for file in os.listdir("cache/"):
                    with open(f"cache/{file}", 'r') as f:
                        file_content = f.read()
                    if file_content == size:
                        Msg = file.split(".txt")[0]
                        print(f"Guessed Pokémon: {Msg}")
                        await guessSolver.send_message(chatid, Msg)
                        last_guess_time = time.time()
                        await asyncio.sleep(10)
                        await send_guess_command()
                        return
                # If the Pokémon data is not in the cache, save its size
                with open("saitama/cache.txt", 'w') as file:
                    file.write(size)
                print("Cached data for new Pokémon.")
    except Exception as e:
        print(f"Error in guessing Pokémon: {e}")

# Save Pokémon data when the game reveals the answer
@guessSolver.on(events.NewMessage(from_users=572621020, pattern="The pokemon was ", chats=int(chatid)))
async def save_pokemon(event):
    global last_guess_time, pending_guess
    try:
        pending_guess = False  # Reset pending status on valid response
        pokemon_name = ((event.message.text).split("The pokemon was **")[1]).split("**")[0]
        print(f"Saving Pokémon: {pokemon_name}")
        with open(f"cache/{pokemon_name}.txt", 'w') as file:
            with open("saitama/cache.txt", 'r') as inf:
                cont = inf.read()
                file.write(cont)
        os.remove("saitama/cache.txt")
        await send_guess_command()
    except Exception as e:
        print(f"Error in saving Pokémon data: {e}")

# Handle "There is already a guessing game being played" message
@guessSolver.on(events.NewMessage(from_users=572621020, pattern="There is already a guessing game being played", chats=int(chatid)))
async def handle_active_game(event):
    print("A guessing game is already active. Retrying shortly...")
    await asyncio.sleep(10)  # Wait 10 seconds before retrying
    await send_guess_command()

# Function to monitor bot behavior and retry if no response
async def monitor_responses():
    global last_guess_time, pending_guess
    while True:
        try:
            async with retry_lock:  # Prevent multiple retries
                # Retry if no response within the timeout period
                if pending_guess and (time.time() - last_guess_time > guess_timeout):
                    print("No response detected after /guess. Retrying...")
                    await send_guess_command()
            await asyncio.sleep(6)  # Check every 6 seconds
        except Exception as e:
            print(f"Error in monitoring responses: {e}")
            await asyncio.sleep(6)

# Reconnection logic with retry limit
async def ensure_connection(max_retries=1000):
    retry_count = 0  # Initialize retry counter
    while retry_count < max_retries:
        try:
            if not guessSolver.is_connected():
                print(f"Reconnecting... Attempt {retry_count + 1}/{max_retries}")
                await guessSolver.connect()
                retry_count += 1
            if not guessSolver.is_user_authorized():
                print("Session expired. Please log in again.")
                break
            retry_count = 0  # Reset counter if successfully connected
            await asyncio.sleep(5)  # Check connection every 5 seconds
        except Exception as e:
            print(f"Error during reconnection attempt {retry_count + 1}: {e}")
            retry_count += 1
            await asyncio.sleep(5)  # Wait before retrying

    if retry_count >= max_retries:
        print(f"Failed to reconnect after {max_retries} attempts. Exiting...")
        return  # Stop the bot after reaching max retries

# Main bot loop
async def main():
    await guessSolver.start()
    print("Bot started. Listening for commands and guessing games...")
    # Automatically start guessing
    await send_guess_command()
    await asyncio.gather(
        ensure_connection(max_retries=1000),  # Ensure the bot stays connected
        monitor_responses(),  # Monitor responses and handle retries
        guessSolver.run_until_disconnected()
    )

if __name__ == "__main__":
    asyncio.run(main())
