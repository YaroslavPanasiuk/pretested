import os
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk

from .library import DataError, load_library
from .results import ResultsStore
from .ui import TestWindow


class TestApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.pretested")
        self.library = None
        self.results = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.load_css()

    def load_css(self):
        # style.css ships inside the package, so this path holds for both a
        # source checkout and an installed copy.
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
        try:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
        except Exception as e:
            print(f"Warning: Failed to load CSS from {css_path}: {e}")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            # Load banks here rather than in __init__ so a failure can be
            # reported in a dialog; nobody sees a message printed to stderr.
            if self.library is None:
                try:
                    self.library = load_library()
                except DataError as e:
                    self.show_fatal_error(str(e))
                    return
                for problem in self.library.problems:
                    print(f"Warning: skipped a question bank -- {problem}")
            if self.results is None:
                self.results = ResultsStore()
            win = TestWindow(app=self, library=self.library,
                             results=self.results)
        win.present()

    def show_fatal_error(self, message):
        # hold() keeps the application alive while the dialog is up; with no
        # window on screen GApplication would otherwise exit immediately.
        self.hold()
        dialog = Gtk.AlertDialog()
        dialog.set_modal(True)
        dialog.set_message("Cannot start Pretested")
        dialog.set_detail(message)
        dialog.set_buttons(["Quit"])

        def on_dismissed(*_args):
            self.release()
            self.quit()

        dialog.choose(None, None, on_dismissed)


def main(argv=None):
    app = TestApp()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    sys.exit(main())
