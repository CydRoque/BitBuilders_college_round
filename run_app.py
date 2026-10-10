"""
Fairwork Application Launcher
Run this script to launch the Fairwork Decentralized Milestone & Delivery Tracking platform.
"""

import sys
import webbrowser
import threading
import time
from backend.app import app, socketio

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("   [+] FAIRWORK: BLOCKCHAIN MILESTONE AGREEMENT & TRACKING PLATFORM   ")
    print("="*70)
    print(" - Built-in Blockchain: SHA-256 Blocks, Merkle Trees & PoW Mining")
    print(" - Escrow Smart Contract: Milestone Conditional Locking & Release")
    print(" - Amazon-Style Tracker: Visual 6-Stage Delivery Pipeline")
    print(" - Fairwork Failover: Automatic Late Penalty & Relinquish/Reassignment")
    print(" - Web Dashboard: http://127.0.0.1:5000")
    print("="*70 + "\n")

    threading.Thread(target=open_browser, daemon=True).start()
    socketio.run(app, host="127.0.0.1", port=5000, debug=False, allow_unsafe_werkzeug=True)
