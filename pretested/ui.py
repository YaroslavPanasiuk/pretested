import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from .attempt import Attempt, MODE_RANDOM, MODE_TEST, sample_questions

RANDOM_SIZES = (("Rand 20", 20), ("Rand 50", 50),
                ("Rand 100", 100), ("Rand all", -1))


class TestWindow(Gtk.ApplicationWindow):
    """Subject sidebar, test selector, question pane and navigation grid.

    Three refresh entry points, each calling into the next:
      rebuild_subject_ui()  -> sidebar, after the library changes
      rebuild_test_ui()     -> test row, after the subject changes
      load_question_ui()    -> question pane, after navigating or answering
    """

    def __init__(self, app, library):
        super().__init__(application=app)
        self.library = library
        self.subject = None
        self.attempt = None
        # Identifies which selector button is currently active, e.g.
        # ("test", "ai_1") or ("random", 50). Replaces the old trick of faking
        # a model index to point at a Rand button's position.
        self.active_token = None

        self.set_default_size(1000, 640)
        self.set_title("Pretested")
        self.set_icon_name("pretested")

        self.root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.root.add_css_class("main-container")
        self.set_child(self.root)

        # -- subject sidebar ----------------------------------------------
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.sidebar_box.add_css_class("sidebar")
        self.sidebar_box.set_size_request(210, -1)
        self.root.append(self.sidebar_box)

        sidebar_title = Gtk.Label(label="Subjects")
        sidebar_title.add_css_class("sidebar-title")
        sidebar_title.set_halign(Gtk.Align.START)
        self.sidebar_box.append(sidebar_title)

        self.sidebar_scroll = Gtk.ScrolledWindow()
        self.sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sidebar_scroll.set_vexpand(True)
        self.sidebar_box.append(self.sidebar_scroll)

        self.subject_list = Gtk.ListBox()
        self.subject_list.add_css_class("subject-list")
        self.subject_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.subject_list.connect("row-selected", self.on_subject_selected)
        self.sidebar_scroll.set_child(self.subject_list)

        # -- main column ---------------------------------------------------
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_hexpand(True)
        self.main_box.add_css_class("content-pane")
        self.root.append(self.main_box)

        self.test_scroll = Gtk.ScrolledWindow()
        self.test_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.test_scroll.set_margin_bottom(10)
        self.main_box.append(self.test_scroll)

        self.test_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.test_box.add_css_class("test-selector-container")
        self.test_scroll.set_child(self.test_box)
        self.test_buttons = []

        self.split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.split_box.set_vexpand(True)
        self.main_box.append(self.split_box)

        self.left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.left_box.set_hexpand(True)
        self.split_box.append(self.left_box)

        self.question_scroll = Gtk.ScrolledWindow()
        self.question_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.question_scroll.set_propagate_natural_height(True)
        self.question_scroll.set_size_request(-1, 280)
        self.left_box.append(self.question_scroll)

        self.question_content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.question_scroll.set_child(self.question_content_box)

        self.progress_label = Gtk.Label()
        self.progress_label.add_css_class("progress-label")
        self.progress_label.set_halign(Gtk.Align.START)
        self.question_content_box.append(self.progress_label)

        self.question_label = Gtk.Label(wrap=True)
        self.question_label.add_css_class("question-label")
        self.question_label.set_halign(Gtk.Align.START)
        self.question_content_box.append(self.question_label)

        self.options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.options_box.add_css_class("options-container")
        self.question_content_box.append(self.options_box)
        self.current_buttons = {}
        self.ordered_buttons = []

        self.feedback_label = Gtk.Label(wrap=True)
        self.feedback_label.set_halign(Gtk.Align.START)
        self.question_content_box.append(self.feedback_label)

        self.nav_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.nav_button_box.add_css_class("nav-buttons")
        self.left_box.append(self.nav_button_box)

        self.score_label = Gtk.Label()
        self.score_label.add_css_class("result-title")
        self.score_label.set_halign(Gtk.Align.START)
        self.left_box.append(self.score_label)

        self.prev_btn = Gtk.Button(label="Previous")
        self.prev_btn.add_css_class("nav-btn")
        self.prev_btn.connect("clicked", self.on_prev)
        self.nav_button_box.append(self.prev_btn)

        self.check_btn = Gtk.Button(label="Check")
        self.check_btn.add_css_class("nav-btn")
        self.check_btn.connect("clicked", self.on_check_answer)
        self.nav_button_box.append(self.check_btn)

        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.add_css_class("nav-btn")
        self.next_btn.connect("clicked", self.on_next)
        self.nav_button_box.append(self.next_btn)

        # -- right column --------------------------------------------------
        self.right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.right_box.set_size_request(240, -1)
        self.split_box.append(self.right_box)

        self.grid_scroll = Gtk.ScrolledWindow()
        self.grid_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.grid_scroll.set_vexpand(True)
        self.right_box.append(self.grid_scroll)

        self.nav_grid = Gtk.Grid(column_spacing=0, row_spacing=0)
        self.nav_grid.set_halign(Gtk.Align.CENTER)
        self.grid_scroll.set_child(self.nav_grid)
        self.nav_buttons = []

        self.action_button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.right_box.append(self.action_button_box)

        self.submit_btn = Gtk.Button(label="Submit Test")
        self.submit_btn.connect("clicked", self.on_submit)
        self.action_button_box.append(self.submit_btn)

        self.reset_btn = Gtk.Button(label="Reset Test")
        self.reset_btn.connect("clicked", self.on_reset)
        self.action_button_box.append(self.reset_btn)

        self.rebuild_subject_ui()

    # ----------------------------------------------------------------------
    # Subjects
    # ----------------------------------------------------------------------

    def rebuild_subject_ui(self):
        while self.subject_list.get_first_child() is not None:
            self.subject_list.remove(self.subject_list.get_first_child())

        self.subject_rows = []
        for subject in self.library:
            row = Gtk.ListBoxRow()
            row.add_css_class("subject-row")
            label = Gtk.Label(label=subject.name, wrap=True, xalign=0.0)
            label.set_halign(Gtk.Align.START)
            row.set_child(label)
            row.subject = subject
            self.subject_list.append(row)
            self.subject_rows.append(row)

        if self.subject_rows:
            keep = self.subject
            target = 0
            if keep is not None:
                for i, row in enumerate(self.subject_rows):
                    if row.subject.id == keep.id:
                        target = i
                        break
            self.subject_list.select_row(self.subject_rows[target])

    def on_subject_selected(self, listbox, row):
        if row is None:
            return
        self.subject = row.subject
        self.active_token = None
        self.rebuild_test_ui()

    # ----------------------------------------------------------------------
    # Tests within the selected subject
    # ----------------------------------------------------------------------

    def rebuild_test_ui(self):
        while self.test_box.get_first_child() is not None:
            self.test_box.remove(self.test_box.get_first_child())
        self.test_buttons = []

        if self.subject is None:
            return

        for test in self.subject.tests:
            btn = Gtk.Button(label=test.name)
            btn.add_css_class("test-btn")
            btn.token = (MODE_TEST, test.id)
            btn.connect("clicked", self.on_test_selected, test)
            self.test_box.append(btn)
            self.test_buttons.append(btn)

        for label, count in RANDOM_SIZES:
            btn = Gtk.Button(label=label)
            btn.add_css_class("test-btn")
            btn.token = (MODE_RANDOM, count)
            btn.connect("clicked", self.on_random_selected, count)
            self.test_box.append(btn)
            self.test_buttons.append(btn)

        if self.active_token is None and self.subject.tests:
            self.select_test(self.subject.tests[0])
        else:
            self.update_selector_styles()

    def update_selector_styles(self):
        for btn in self.test_buttons:
            if btn.token == self.active_token:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    def attempt_for_test(self, test):
        return Attempt(test.questions, title=f"{test.subject_name} — {test.name}",
                       mode=MODE_TEST, subject_id=test.subject_id,
                       test_key=test.key)

    def select_test(self, test):
        """Start a test and mark its selector button active.

        Both the click handler and the initial load go through here so the
        highlight can never drift out of sync with the running attempt.
        """
        self.active_token = (MODE_TEST, test.id)
        self.start_attempt(self.attempt_for_test(test))

    def on_test_selected(self, button, test):
        self.select_test(test)

    def on_random_selected(self, button, count):
        questions = sample_questions(self.subject.questions, count)
        shown = len(questions)
        self.active_token = button.token
        self.start_attempt(Attempt(
            questions,
            title=f"{self.subject.name} — Random mix ({shown})",
            mode=MODE_RANDOM,
            subject_id=self.subject.id,
            test_key=f"{self.subject.id}/random",
        ))

    # ----------------------------------------------------------------------
    # The attempt
    # ----------------------------------------------------------------------

    def start_attempt(self, attempt):
        self.attempt = attempt
        self.update_selector_styles()
        self.score_label.set_text("")
        self.submit_btn.set_sensitive(True)
        self.rebuild_nav_grid()

    def rebuild_nav_grid(self):
        while self.nav_grid.get_first_child() is not None:
            self.nav_grid.remove(self.nav_grid.get_first_child())
        self.nav_buttons.clear()

        for i in range(self.attempt.total):
            btn = Gtk.Button(label=str(i + 1))
            btn.connect("clicked", self.on_nav_grid_clicked, i)
            self.nav_buttons.append(btn)
            self.nav_grid.attach(btn, i % 5, i // 5, 1, 1)

        self.load_question_ui()

    def update_nav_grid_styles(self):
        for i, btn in enumerate(self.nav_buttons):
            classes = ["grid-nav-btn"]

            if self.attempt.is_revealed(i):
                classes.append("correct" if self.attempt.is_correct(i) else "incorrect")
            elif self.attempt.get_answer(i):
                classes.append("answered")
            elif i in self.attempt.visited:
                classes.append("visited")
            else:
                classes.append("unvisited")

            if i == self.attempt.current_idx:
                classes.append("active")

            btn.set_css_classes(classes)

    def load_question_ui(self):
        self.attempt.mark_visited()
        question = self.attempt.current()

        self.progress_label.set_text(
            f"{self.attempt.title}    "
            f"Question {self.attempt.current_idx + 1} of {self.attempt.total}    "
            f"Answered {self.attempt.answered_count()}/{self.attempt.total}"
        )
        self.question_label.set_text(question.text)

        self.feedback_label.set_text("")
        self.feedback_label.remove_css_class("feedback-correct")
        self.feedback_label.remove_css_class("feedback-incorrect")

        while self.options_box.get_first_child() is not None:
            self.options_box.remove(self.options_box.get_first_child())

        self.current_buttons.clear()
        self.ordered_buttons = []

        is_revealed = self.attempt.is_revealed()

        first_button = None
        for position, (key, text) in enumerate(question.options, start=1):
            cb = Gtk.CheckButton(label=f"{position}.  {text}")
            if first_button:
                cb.set_group(first_button)
            else:
                first_button = cb

            self.current_buttons[key] = cb
            self.ordered_buttons.append(cb)
            cb.connect("toggled", self.on_option_toggled, key)

            if is_revealed:
                cb.set_sensitive(False)

            self.options_box.append(cb)

        saved_answer = self.attempt.get_answer()
        if saved_answer and saved_answer in self.current_buttons:
            self.current_buttons[saved_answer].set_active(True)

        if is_revealed:
            if saved_answer == question.answer:
                self.feedback_label.set_text("You answered this correctly.")
                self.feedback_label.add_css_class("feedback-correct")
            else:
                self.feedback_label.set_text(f"Correct answer: {question.answer_text}")
                self.feedback_label.add_css_class("feedback-incorrect")

        self.check_btn.set_sensitive(self.attempt.can_check())
        self.prev_btn.set_sensitive(self.attempt.current_idx > 0)
        self.next_btn.set_sensitive(self.attempt.current_idx < self.attempt.total - 1)
        self.update_nav_grid_styles()

    # ----------------------------------------------------------------------
    # Handlers
    # ----------------------------------------------------------------------

    def on_option_toggled(self, button, key):
        if button.get_active() and not self.attempt.submitted:
            self.attempt.set_answer(key)
            self.check_btn.set_sensitive(self.attempt.can_check())
            self.update_nav_grid_styles()

    def on_check_answer(self, button):
        if self.attempt.check():
            self.load_question_ui()

    def on_nav_grid_clicked(self, button, index):
        self.attempt.navigate(index)
        self.load_question_ui()

    def on_prev(self, button):
        self.attempt.prev_question()
        self.load_question_ui()

    def on_next(self, button):
        self.attempt.next_question()
        self.load_question_ui()

    def on_reset(self, button):
        self.attempt.reset()
        self.score_label.set_text("")
        self.submit_btn.set_sensitive(True)
        self.rebuild_nav_grid()

    def on_submit(self, button):
        score, total = self.attempt.submit()
        self.submit_btn.set_sensitive(False)
        self.score_label.set_text(f"Test Complete! Final Score: {score} / {total}")
        self.load_question_ui()
