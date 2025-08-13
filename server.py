import socket
import threading
import random
import time
import os

# Server configuration
HOST = '127.0.0.1'  # Localhost IP address
PORT = 65432  # Port number for server
MAX_PLAYERS = 4  # Maximum number of players allowed
MIN_PLAYERS = 4  # Minimum players required to start (must have exactly 4)
ROUND_TIME = 5  # Time limit for each turn in seconds
LIVES_PER_PLAYER = 3  # Number of lives each player starts with


def load_words():
    """
    Load words from words.txt file with error handling.
    Returns a set of lowercase words for dictionary validation.
    """
    try:
        # Try to open words.txt in current directory
        with open("words.txt") as f:
            return set(word.strip().lower() for word in f if len(word.strip()) > 1) # Only loads words with length >1
    except FileNotFoundError:
        # If not found in current directory, try with full path
        script_dir = os.path.dirname(os.path.abspath(__file__)) #what is this?
        words_path = os.path.join(script_dir, "words.txt")
        try:
            with open(words_path) as f:
                return set(word.strip().lower() for word in f)
        except FileNotFoundError:
            print("Error: words.txt not found!")
            print(f"Looking for file in: {script_dir}")
            return set()


def get_random_sequence(words):
    """
    Generate a random 2-3 letter combination from the word list.
    Args:
        words: Set of valid words to choose from
    Returns:
        String of 2-3 letters to be used as sequence
    """
    if not words:
        return "ab"  # Fallback if no words loaded
    word = random.choice(list(words))
    if len(word) == 2: #prevents doing substring 3 of length 2 words
        # Use entire 2-letter word as sequence
        return word
    length = random.randint(2, 3)  # Randomly choose 2 or 3 letters
    start = random.randint(0, len(word) - length) #0-length - (2 or 3)
    return word[start:start + length]

class Player:
    """
    Player class to store information about each connected player.
    """

    def __init__(self, conn, addr, name):
        self.conn = conn  # Socket connection to player
        self.addr = addr  # Player's address
        self.name = name  # Player's name
        self.active = True  # Whether player is still in game #what is the difference between active and disconnected?
        self.lives = LIVES_PER_PLAYER  # Number of lives remaining
        self.disconnected = False  # Whether player has disconnected


def broadcast(players, msg):
    """
    Send a message to all active and connected players.
    Args:
        players: List of Player objects
        msg: Message string to send
    """
    msg = msg.replace("\\n", "\n") #makes sure it actually prints a new line
    for p in players:
        if p.active and not p.disconnected:
            try:
                p.conn.sendall(msg.encode())
            except Exception as e:
                p.disconnected = True
                p.active = False #and what happens if this


def send_to_player(player, msg):
    """
    Send a message to a specific player.
    Args:
        player: Player object to send message to
        msg: Message string to send
    """
    msg = msg.replace("\\n", "\n")  # makes sure it actually prints a new line
    if player.active and not player.disconnected:
        try:
            player.conn.sendall(msg.encode())
        except Exception as e:
            player.disconnected = True
            player.active = False


def handle_player(player, players, lock, game_started):
    """
    Handle communication with a single player in a separate thread.
    Listens for player input and handles disconnections.
    Args:
        player: Player object to handle
        players: List of all players
        lock: Threading lock for synchronization --> not sure what this is but okay
        game_started: List containing boolean flag for game state
    """
    while True:
        if game_started[0]:
            return #makes sure this thread actually stops when the game starts
        try:
            # Receive data from player
            data = player.conn.recv(1024)
            if not data:
                break
            if not game_started[0]:
                # Before game starts, check for 'start' command
                msg = data.decode().strip().lower()
                if msg == "start" and len([p for p in players if p.active and not p.disconnected]) >= MIN_PLAYERS:
                    game_started[0] = True
                    broadcast(players, f"\n{player.name} started the game!\n")
                    # Stop listening after game starts - main loop will handle input
                    return  # Exit normally, don't mark as disconnected
        except:
            break

    # Only reach here if player actually disconnected
    player.disconnected = True
    player.active = False
    print(f"ERROR: {player.name} disconnected bitch!")
    broadcast(players, f"\nERROR: {player.name} disconnected! Server will shut down.\n")

    # Kill server if any player disconnects (as per requirements)
    for p in players:
        try:
            p.conn.close()
        except:
            pass
    print("Server shutting down due to player disconnect.") #should players force exit if they disconnect too?
    os._exit(1)  # Force exit


def main():
    """
    Main server function that handles the entire game flow.
    """
    # Load the word dictionary
    print("Loading words.txt...")
    WORDS = load_words()
    if not WORDS:
        print("Failed to load words. Exiting.")
        return
    print(f"Loaded {len(WORDS)} words successfully!")

    # Setup the server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Server started on {HOST}:{PORT}")
    print(f"Waiting for exactly {MIN_PLAYERS} players...")

    # Initialize game variables
    players = []
    lock = threading.Lock() #what is threading
    game_started = [False]  # Use list to make it mutable in threads

    # Accept exactly 4 players
    while len(players) < MAX_PLAYERS and not game_started[0]:
        conn, addr = server.accept()
        conn.sendall(b"Enter your name: ")
        name = conn.recv(1024).decode().strip()
        player = Player(conn, addr, name)
        players.append(player)
        print(f"{name} joined from {addr}")

        #Starts a separate thread for every player
        threading.Thread(target=handle_player, args=(player, players, lock, game_started), daemon=True).start()

        # Send welcome message with player count
        active_count = len([p for p in players if p.active and not p.disconnected])
        conn.sendall(f"Welcome, {name}! ({active_count}/{MAX_PLAYERS} players)\n".encode())
        if active_count >= MIN_PLAYERS:
            conn.sendall(f"Type 'start' to begin the game (need exactly {MIN_PLAYERS} players)\n".encode())
        else:
            conn.sendall(f"Waiting for {MIN_PLAYERS - active_count} more players...\n".encode())

    # Wait for game to start (someone types 'start')
    while not game_started[0] and len([p for p in players if p.active and not p.disconnected]) >= MIN_PLAYERS:
        time.sleep(0.1)

    if not game_started[0]:
        print("Not enough players to start. Shutting down.")
        for p in players:
            p.conn.close() #missing this line for disconnect players?
        server.close()
        return

    # Game starts! Initialize game variables
    active_players = [p for p in players if p.active and not p.disconnected]
    used_words = set()  # Track words that have been used
    last_word_valid = True  # Track if previous word was valid (affects sequence generation)

    print(f"[DEBUG] Game started! Active players: {[p.name for p in active_players]}")

    # Keep the handle_player threads running for communication
    print(f"[DEBUG] Keeping handle_player threads active")

    # Show game start message to all players
    player_names = [p.name for p in active_players]
    print(f"[DEBUG] About to send game start messages to: {player_names}")
    time.sleep(0.5)  # Small delay to ensure connections are ready
    broadcast(players, f"=== GAME STARTED ===\n")
    time.sleep(0.1)
    broadcast(players, f"Players: {', '.join(player_names)}\n")
    time.sleep(0.1)
    broadcast(players, f"Rules: Each player has {LIVES_PER_PLAYER} lives\n")
    time.sleep(0.1)
    broadcast(players, f"Type a word containing the given sequence within {ROUND_TIME} seconds\n")
    time.sleep(0.1)
    broadcast(players, f"Used words cannot be repeated\n")
    time.sleep(0.1)
    broadcast(players, f"Last player with lives wins!\n")
    time.sleep(0.1)

    # Main game loop
    turn = 0
    round_num = 1

    print(f"[DEBUG] Starting game loop with {len(active_players)} players")

    # Continue until only one player has lives remaining
    ######MAIN GAME--------------------------------------------------------------------------------------------------------------------------

    while len([p for p in active_players if p.active and not p.disconnected and p.lives > 0]) > 1: #while there are 2 players connected and alive
        print(f"[DEBUG] Game loop iteration {turn}")
        player = active_players[turn % len(active_players)] #turn increments every player change
        print(f"[DEBUG] Current player: {player.name}")

        # Skip players with no lives
        if player.lives <= 0 or not player.active or player.disconnected: #doesn't the server shut down if someone disconnects?
            print(
                f"[DEBUG] Skipping {player.name} - lives: {player.lives}, active: {player.active}, disconnected: {player.disconnected}")
            turn += 1
            continue

        # Only generate new sequence if previous word was valid
        if last_word_valid:
            seq = get_random_sequence(WORDS)
            print(f"[DEBUG] Generated new sequence: {seq}")
        else:
            # Use same sequence if previous word was invalid
            print(f"[DEBUG] Using same sequence: {seq}")
            pass  # seq remains the same

        # Show current game state to all players
        remaining_players = [f"{p.name}({p.lives})" for p in active_players if
                             p.active and not p.disconnected and p.lives > 0]
        print(f"[DEBUG] Remaining players: {remaining_players}")
        broadcast(players, f"=== ROUND {round_num} ===\n")
        broadcast(players, f"Remaining players: {', '.join(remaining_players)} \n")
        broadcast(players, f"Turn: {player.name} (Lives: {player.lives}) \n")

        # Send turn message to current player
        msg = f"Your turn, {player.name}! Sequence: '{seq}' (You have {ROUND_TIME} seconds) \n"
        msg += f"Type your word now: "
        print(f"[DEBUG] Sending turn message to {player.name}")
        send_to_player(player, msg)

        # Show other players whose turn it is
        print(f"[DEBUG] Broadcasting turn info to other players")
        broadcast([p for p in active_players if p != player and p.active and not p.disconnected],
                  f"{player.name}'s turn! Sequence: '{seq}' \n")

        # Wait for player response with timeout
        print(f"[DEBUG] Waiting for {player.name}'s response...")
        print(f"[DEBUG] Socket timeout set to {ROUND_TIME} seconds")
        player.conn.settimeout(ROUND_TIME)
        data = None  # Initialize data variable
        word = ""  # Initialize word variable
        try:
            print(f"[DEBUG] About to read from {player.name}'s socket...")
            data = player.conn.recv(1024)
            print(f"[DEBUG] Raw data received: {repr(data)}")
            if data:
                word = data.decode().strip().lower()
                print(f"[DEBUG] {player.name} entered: '{word}'")
            else:
                word = ""
                print(f"[DEBUG] No data received from {player.name}")
        except socket.timeout:
            word = ""  # Empty string indicates timeout
            print(f"[DEBUG] {player.name} timed out")
        except Exception as e:
            print(f"[DEBUG] Error reading from {player.name}: {e}")
            word = ""
        player.conn.settimeout(None) #what is this? moves on if entered empty string?
        print(f"[DEBUG] Socket timeout cleared")

        # Check if player disconnected during their turn
        if player.disconnected:
            print(f"ERROR: {player.name} disconnected during turn!")
            broadcast(players, f"ERROR: {player.name} disconnected! Server will shut down.")
            for p in players:
                try:
                    p.conn.close() #connection closed but program still running?
                except:
                    pass
            print("Server shutting down due to player disconnect.")
            os._exit(1)

        # Process player's response
        print(f"[DEBUG] Processing {player.name}'s response: '{word}'")
        #if player didn't answer/timed out:
        if word == "":
            # Timeout - player loses a life
            print(f"[DEBUG] {player.name} timed out - losing life")
            player.lives -= 1
            send_to_player(player, f"TIMEOUT! You lose a life. Lives remaining: {player.lives}") #why the weird characters?
            broadcast([p for p in active_players if p != player and p.active and not p.disconnected],
                      f"{player.name} timed out! Lives remaining: {player.lives}\n")
            last_word_valid = False
        elif (seq in word) and (word in WORDS) and (word not in used_words):
            # Valid word - player keeps their life
            print(f"[DEBUG] {player.name} answered correctly: '{word}'")
            used_words.add(word)
            send_to_player(player, f"Correct! '{word}' is valid.\n") #why weird characters?
            broadcast([p for p in active_players if p != player and p.active and not p.disconnected],
                      f"{player.name} answered: '{word}'\n")
            last_word_valid = True
        else:
            # Invalid word - player loses a life
            print(f"[DEBUG] {player.name} answered incorrectly: '{word}'")
            player.lives -= 1
            if word == "":
                reason = "TIMEOUT" #this is shown to player second time
            elif seq not in word:
                reason = f"Word doesn't contain '{seq}'"
            elif word not in WORDS:
                reason = "Not a valid word"
            elif word in used_words:
                reason = "Word already used"
            else:
                reason = "Invalid word"

            send_to_player(player, f"Wrong! {reason}. You lose a life. Lives remaining: {player.lives}\n")
            broadcast([p for p in active_players if p != player and p.active and not p.disconnected],
                      f"{player.name} is wrong! ({reason}) Lives remaining: {player.lives}\n")
            last_word_valid = False

        # Move to next player
        turn += 1
        if turn % len(active_players) == 0:
            round_num += 1

        # Small delay to ensure socket is ready for next read
        time.sleep(0.1)
    ###END WHILE -----------------------------------------------------------
    # Game over - find the winner
    winner = [p for p in active_players if p.active and not p.disconnected and p.lives > 0][0]
    broadcast(players, f"\n=== GAME OVER ===\n")
    broadcast(players, f"Winner: {winner.name}!! Congrats")
    broadcast(players, f"Thanks for playing!\n")

    # Give option to quit or start new game
    print("\nGame over! Type 'quit' to shut down server, or press Enter to start a new game:") #shouldn't this be shown to players?
    try:
        choice = input().strip().lower()
        if choice == 'quit':
            print("Shutting down server...")
            for p in players:
                p.conn.close()
            server.close()
        else:
            print("Starting new game...")
            #does this properly restart the game and connect everyone?
            main()  # Restart the game
            #this calls main recursively... not the best
    except:
        print("Shutting down server...")
        for p in players:
            p.conn.close()
        server.close()


if __name__ == "__main__":
    main()