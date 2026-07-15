import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

class TestWindow(Gtk.ApplicationWindow):
    def __init__(self, app, model):
        super().__init__(application=app)
        self.model = model
        self.set_default_size(800, 600)
        self.set_title("Pretested")
        self.set_icon_name("pretested-app")

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.add_css_class("main-container")
        self.set_child(self.box)

        self.test_scroll = Gtk.ScrolledWindow()
        self.test_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.test_scroll.set_margin_bottom(10)
        self.box.append(self.test_scroll)

        self.test_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.test_box.add_css_class("test-selector-container")
        self.test_scroll.set_child(self.test_box)
        
        self.test_buttons = []
        for i, name in enumerate(self.model.get_test_names()):
            btn = Gtk.Button(label=name)
            btn.add_css_class("test-btn")
            btn.connect("clicked", self.on_test_selected, i)
            self.test_box.append(btn)
            self.test_buttons.append(btn)

        self.split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.split_box.set_vexpand(True)
        self.box.append(self.split_box)

        self.left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.left_box.set_hexpand(True)
        self.split_box.append(self.left_box)

        self.question_scroll = Gtk.ScrolledWindow()
        self.question_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.question_scroll.set_propagate_natural_height(True)
        self.question_scroll.set_size_request(-1, 250)
        self.left_box.append(self.question_scroll)
        
        self.question_content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.question_scroll.set_child(self.question_content_box)

        self.question_label = Gtk.Label(wrap=True)
        self.question_label.add_css_class("question-label")
        self.question_label.set_halign(Gtk.Align.START)
        self.question_content_box.append(self.question_label)

        self.options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.question_content_box.append(self.options_box)
        self.current_buttons = {}

        self.feedback_label = Gtk.Label(wrap=False)
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
        self.prev_btn.connect("clicked", self.on_prev)
        self.nav_button_box.append(self.prev_btn)

        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.connect("clicked", self.on_next)
        self.nav_button_box.append(self.next_btn)

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

        self.rebuild_test_ui()

    def on_test_selected(self, button, index):
        self.model.load_test(index)
        self.rebuild_test_ui()
        
    def on_reset(self, button):
        self.model.reset_test()
        self.rebuild_test_ui()

    def rebuild_test_ui(self):
        for i, btn in enumerate(self.test_buttons):
            if i == self.model.current_test_idx:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

        self.score_label.set_text("")
        self.submit_btn.set_sensitive(True)

        while self.nav_grid.get_first_child() is not None:
            self.nav_grid.remove(self.nav_grid.get_first_child())
            
        self.nav_buttons.clear()
        
        for i in range(self.model.get_total_questions()):
            btn = Gtk.Button(label=str(i + 1))
            btn.connect("clicked", self.on_nav_grid_clicked, i)
            self.nav_buttons.append(btn)
            
            row = i // 5
            col = i % 5
            self.nav_grid.attach(btn, col, row, 1, 1)

        self.load_question_ui()

    def update_nav_grid_styles(self):
        for i, btn in enumerate(self.nav_buttons):
            classes = ["grid-nav-btn"]
            
            if self.model.submitted:
                if self.model.is_correct(i):
                    classes.append("correct")
                else:
                    classes.append("incorrect")
            else:
                if self.model.get_answer(i):
                    classes.append("answered")
                elif i in self.model.visited_questions:
                    classes.append("visited")
                else:
                    classes.append("unvisited")
            
            if i == self.model.current_q_idx:
                classes.append("active")
                
            btn.set_css_classes(classes)
            

    def load_question_ui(self):
        self.model.mark_visited()
        q_data = self.model.get_current_question()
        
        self.question_label.set_text(f"{q_data['question']}")

        self.feedback_label.set_text("")
        self.feedback_label.remove_css_class("feedback-correct")
        self.feedback_label.remove_css_class("feedback-incorrect")

        while self.options_box.get_first_child() is not None:
            self.options_box.remove(self.options_box.get_first_child())

        self.current_buttons.clear()

        first_button = None
        for opt in q_data["options"]:
            for key, val in opt.items():
                cb = Gtk.CheckButton(label=f"{key}: {val}")
                if first_button:
                    cb.set_group(first_button)
                else:
                    first_button = cb
                
                self.current_buttons[key] = cb
                cb.connect("toggled", self.on_option_toggled, key)
                
                if self.model.submitted:
                    cb.set_sensitive(False)
                    
                self.options_box.append(cb)

        saved_answer = self.model.get_answer()
        if saved_answer and saved_answer in self.current_buttons:
            self.current_buttons[saved_answer].set_active(True)

        if self.model.submitted:
            correct_ans = q_data["answer"]
            if saved_answer == correct_ans:
                self.feedback_label.set_text("You answered this correctly.")
                self.feedback_label.add_css_class("feedback-correct")
            else:
                user_text = saved_answer if saved_answer else "No answer"
                self.feedback_label.set_text(f"Your answer: {user_text} | Correct answer: {correct_ans}")
                self.feedback_label.add_css_class("feedback-incorrect")

        self.prev_btn.set_sensitive(self.model.current_q_idx > 0)
        self.next_btn.set_sensitive(self.model.current_q_idx < self.model.get_total_questions() - 1)
        self.update_nav_grid_styles()

    def on_option_toggled(self, button, key):
        if button.get_active() and not self.model.submitted:
            self.model.set_answer(key)
            self.update_nav_grid_styles()

    def on_nav_grid_clicked(self, button, index):
        self.model.navigate(index)
        self.load_question_ui()

    def on_prev(self, button):
        self.model.prev_question()
        self.load_question_ui()

    def on_next(self, button):
        self.model.next_question()
        self.load_question_ui()

    def on_submit(self, button):
        score, total = self.model.submit()
        self.submit_btn.set_sensitive(False)
        self.score_label.set_text(f"Test Complete! Final Score: {score} / {total}")
        self.load_question_ui()