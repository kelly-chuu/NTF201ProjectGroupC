import socket
import threading
import sys

HOST = '127.0.0.1'
PORT = 65432

def listen(sock):
    """Listen for messages from the server"""
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                break
            message = data.decode()
            #print(f"[DEBUG] Received: {repr(message)}") #this just prints it twice...
            print(message, end="", flush=True)
        except Exception as e:
            print(f"[DEBUG] Listen error: {e}")
            break

def main():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        print("Connected to server!")

        # Start listening thread
        threading.Thread(target=listen, args=(sock,), daemon=True).start()

        # Main input loop
        while True:
            try:
                msg = input()
                sock.sendall(msg.encode())
            except KeyboardInterrupt:
                print("\nDisconnecting...")
                break
            except:
                break

    except ConnectionRefusedError:
        print("Could not connect to server. Make sure server.py is running.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            sock.close()
        except:
            pass

if __name__ == "__main__":
    main()