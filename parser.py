import threading
import queue
import json
import os
from PyQt5.QtWidgets import QInputDialog, QMessageBox

class OutputParser:
    def __init__(self):
        pass

    def parse(self,line):
        """Helper to parse a single 'info' line into a dictionary."""
        info_dict = {}
        parts = line.split(" ")
        i = 1 # Start from index 1 because parts[0] is "info"
        while i < len(parts):
            key = parts[i]
            if key == "depth":
                info_dict["depth"] = int(parts[i+1])
                i += 2
            elif key == "seldepth":
                info_dict["seldepth"] = int(parts[i+1])
                i += 2
            elif key == "time":
                info_dict["time_ms"] = int(parts[i+1])
                i += 2
            elif key == "nodes":
                info_dict["nodes"] = int(parts[i+1])
                i += 2
            elif key == "nps":
                info_dict["nps"] = int(parts[i+1])
                i += 2
            elif key == "score":
                score_type = parts[i+1]
                value = int(parts[i+2])
                info_dict["score"] = {"type": score_type, "value": value}
                i += 3
            elif key == "multipv":
                info_dict["multipv"] = int(parts[i+1])
                i += 2
            elif key == "pv":
                pv_moves = []
                j = i + 1
                # Read all subsequent parts until a new keyword or end of line
                while j < len(parts) and parts[j] not in ["depth", "seldepth", "time", "nodes", "nps", "score", "multipv", "currmove", "currmovenumber", "hashfull", "nps", "string", "refutation", "limit", "bestmove", "ponder"]:
                    pv_moves.append(parts[j])
                    j += 1
                info_dict["pv"] = pv_moves
                i = j # Move main index to where PV reading stopped
            elif key == "string": # For info strings that are just messages
                info_dict["message"] = " ".join(parts[i+1:])
                i = len(parts) # Consume rest of the line
            else:
                # Handle other keywords or simply advance to avoid infinite loop
                # For unknown keywords, you might just store the value if it exists
                if i + 1 < len(parts) and not parts[i+1].isalpha(): # Check if next part might be a value
                        info_dict[key] = parts[i+1] # Store as string, can convert later
                        i += 2
                else: # Just the key, no obvious value following immediately
                    info_dict[key] = True # Indicate presence of the key
                    i += 1
        return info_dict
        

    def _enqueue_output(self, out_stream, q):
        """Reads lines from Stockfish's stdout and puts them into a queue."""
        for line in iter(out_stream.readline, ''):
            q.put(line)
        out_stream.close()

    def output(self, board_fen, process, timeout=1.0):
        q = queue.Queue()
        t = threading.Thread(target=self._enqueue_output, args=(process.stdout, q), daemon=True)
        t.start()

        llm_data = {
            "stockfish_analysis": {
                "thinking_process_info_lines": [],
                "best_move_uci": None,
                "best_move_san": None,
                "ponder_move_uci": None,
            },
        }

        best_move_found = False
        while not best_move_found:
            try:
                line = q.get(timeout=timeout).strip()
            except queue.Empty:
                continue

            if line.startswith("info"):
                parsed = self.parse(line)
                if parsed:
                    llm_data["stockfish_analysis"]["thinking_process_info_lines"].append(parsed)

            elif line.startswith("bestmove"):
                parts = line.split()
                llm_data["stockfish_analysis"]["best_move_uci"] = parts[1]
                if len(parts) > 3 and parts[2] == "ponder":
                    llm_data["stockfish_analysis"]["ponder_move_uci"] = parts[3]
                best_move_found = True

        return llm_data

class Conversations:
    def __init__(self, parent_window=None):
        self.conversations = {}
        self.parent_window = parent_window  # Reference to main window for dialogs
        self.filename = None  # Will be set by user input
        self.ask_for_filename()  # Prompt user for filename on init

    def ask_for_filename(self):
        """Prompt user for filename using a dialog"""
        if self.parent_window:
            filename, ok = QInputDialog.getText(
                self.parent_window,
                "Save Conversations",
                "Enter a name for your conversation file:",
                text="chess_conversations"  # Default name
            )
            if ok and filename:
                self.filename = f"{filename}.json"
            else:
                # Use default if user cancels
                self.filename = "chess_conversations.json"
            self.load_conversations()

    def record_conversation(self, model, language, question, response):
        if model not in self.conversations:
            self.conversations[model] = {}
        if language not in self.conversations[model]:
            self.conversations[model][language] = []
        
        self.conversations[model][language].append((question, response))
        self.save_conversations()

    def get_conversations(self, model, language):
        if model in self.conversations and language in self.conversations[model]:
            return self.conversations[model][language]
        return []

    def save_conversations(self):
        """Save conversations to the user-specified JSON file"""
        if not self.filename:
            return
            
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.conversations, f)
        except Exception as e:
            if self.parent_window:
                QMessageBox.warning(
                    self.parent_window,
                    "Save Error",
                    f"Could not save conversations: {str(e)}"
                )

    def load_conversations(self):
        """Load conversations from the user-specified JSON file"""
        if not self.filename or not os.path.exists(self.filename):
            return
            
        try:
            with open(self.filename, 'r') as f:
                self.conversations = json.load(f)
        except Exception as e:
            if self.parent_window:
                QMessageBox.warning(
                    self.parent_window,
                    "Load Error",
                    f"Could not load conversations: {str(e)}"
                )
            self.conversations = {}