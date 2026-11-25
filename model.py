import json
import os
import random
import copy
import shutil


class DataError(Exception):
    """Raised when the question bank is missing or malformed."""


class TestModel:
    def __init__(self, filename="tests.json"):
        config_home = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        self.config_dir = os.path.join(config_home, 'pretested')
        self.filepath = os.path.join(self.config_dir, filename)

        self._ensure_config_exists(filename)

        self.tests_data = self._load_tests(self.filepath)
        if not self.tests_data or "tests" not in self.tests_data:
            raise DataError(f"Invalid or missing question bank at {self.filepath}")
        if not self.tests_data["tests"]:
            raise DataError(f"No tests found in {self.filepath}")


        self.current_test_idx = 0
        self.load_test(0)

    def _ensure_config_exists(self, filename):
        if not os.path.exists(self.filepath):
            os.makedirs(self.config_dir, exist_ok=True)
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            nix_default_path = os.path.join(script_dir, "..", "share", "pretested", filename)
            
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
        except (OSError, json.JSONDecodeError) as e:
            raise DataError(f"Could not read {filepath}: {e}") from e

    def get_test_names(self):
        return [t["name"] for t in self.tests_data["tests"]]

    def load_test(self, test_idx):
        self.current_test_idx = test_idx
        self.current_test = self.tests_data["tests"][test_idx]
        self.reset_test()

    def reset_test(self):
        # Use deepcopy to prevent mutating the original loaded JSON data
        self.questions = copy.deepcopy(self.current_test["questions"])
        random.shuffle(self.questions)
        
        # Shuffle the options for each question
        for q in self.questions:
            if "options" in q:
                random.shuffle(q["options"])
        
        self.current_q_idx = 0
        self.user_answers = {} 
        self.visited_questions = set()
        self.checked_questions = set() 
        self.submitted = False

    def can_check(self):
        # Checking reveals the answer and locks the question for good, so refuse
        # it while nothing is selected -- otherwise a stray click scores the
        # question wrong with no way back short of a full reset.
        return (
            not self.submitted
            and self.current_q_idx not in self.checked_questions
            and self.get_answer() is not None
        )

    def check_current_answer(self):
        if not self.can_check():
            return False
        self.checked_questions.add(self.current_q_idx)
        return True

    def set_answer(self, key):
        # Update this method to check for locks
        if not self.submitted and self.current_q_idx not in self.checked_questions:
            self.user_answers[self.current_q_idx] = key

    def get_total_questions(self):
        return len(self.questions)

    def get_current_question(self):
        return self.questions[self.current_q_idx]

    def mark_visited(self):
        self.visited_questions.add(self.current_q_idx)

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
    
    def load_random_mixed_test(self, sample_size=30):
        all_questions = []
        for test in self.tests_data["tests"]:
            all_questions.extend(test.get("questions", []))
        
        if sample_size == -1:
            actual_sample_size = len(all_questions)
        else:
            actual_sample_size = min(sample_size, len(all_questions))
        selected_questions = random.sample(all_questions, actual_sample_size)
        
        # Create a virtual test dictionary
        self.current_test = {
            "name": f"Random Mix ({sample_size})",
            "questions": selected_questions
        }

        self.reset_test()