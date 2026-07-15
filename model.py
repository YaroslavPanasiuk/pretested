import json
import sys
import os
import random
import shutil

class TestModel:
    def __init__(self, filename="tests.json"):
        config_home = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        self.config_dir = os.path.join(config_home, 'school-test-app')
        self.filepath = os.path.join(self.config_dir, filename)

        self._ensure_config_exists(filename)

        self.tests_data = self._load_tests(self.filepath)
        if not self.tests_data or "tests" not in self.tests_data:
            print(f"Error: Invalid or missing file at {self.filepath}")
            sys.exit(1)
            
        self.current_test_idx = 0
        self.load_test(0)

    def _ensure_config_exists(self, filename):
        if not os.path.exists(self.filepath):
            os.makedirs(self.config_dir, exist_ok=True)
            
            # Locate default tests.json relative to the executable in Nix store
            # Executable is in $out/bin/, asset is in $out/share/school-test-app/
            script_dir = os.path.dirname(os.path.abspath(__file__))
            nix_default_path = os.path.join(script_dir, "..", "share", "school-test-app", filename)
            
            # Fallback for local development if not running from Nix store
            local_default_path = filename

            if os.path.exists(nix_default_path):
                shutil.copy2(nix_default_path, self.filepath)
            elif os.path.exists(local_default_path):
                shutil.copy2(local_default_path, self.filepath)
            else:
                print(f"Warning: Default template {filename} not found.")

    def _load_tests(self, filepath):
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return None

    def get_test_names(self):
        return [t["name"] for t in self.tests_data["tests"]]

    def load_test(self, test_idx):
        self.current_test_idx = test_idx
        self.current_test = self.tests_data["tests"][test_idx]
        self.reset_test()

    def reset_test(self):
        self.questions = list(self.current_test["questions"])
        random.shuffle(self.questions)
        
        self.current_q_idx = 0
        self.user_answers = {} 
        self.visited_questions = set()
        self.submitted = False

    def get_total_questions(self):
        return len(self.questions)

    def get_current_question(self):
        return self.questions[self.current_q_idx]

    def mark_visited(self):
        self.visited_questions.add(self.current_q_idx)

    def set_answer(self, key):
        if not self.submitted:
            self.user_answers[self.current_q_idx] = key

    def get_answer(self, idx=None):
        if idx is None:
            idx = self.current_q_idx
        return self.user_answers.get(idx)

    def is_correct(self, idx):
        return self.user_answers.get(idx) == self.questions[idx]["answer"]

    def navigate(self, index):
        if 0 <= index < self.get_total_questions():
            self.current_q_idx = index

    def next_question(self):
        self.navigate(self.current_q_idx + 1)

    def prev_question(self):
        self.navigate(self.current_q_idx - 1)

    def submit(self):
        self.submitted = True
        score = sum(1 for i in range(self.get_total_questions()) if self.is_correct(i))
        return score, self.get_total_questions()